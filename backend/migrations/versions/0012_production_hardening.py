"""Production hardening: MFA lockout, operator protection and owner-managed WhatsApp."""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

ARCHIVE_FUNCTION = "public.archive_platform_user(uuid)"
LOGIN_FUNCTION = "public.set_platform_user_login(uuid,text)"
DELIVERY_FUNCTION = "public.set_clinic_whatsapp_delivery(uuid,boolean)"


def upgrade() -> None:
    # Bloqueio temporário após falhas seguidas do autenticador, contadas por conta.
    op.execute("ALTER TABLE users ADD COLUMN mfa_failures integer NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE users ADD COLUMN mfa_locked_until timestamptz")
    op.execute("ALTER TABLE users ADD CONSTRAINT users_mfa_failures CHECK (mfa_failures >= 0)")
    op.execute("GRANT UPDATE(mfa_failures, mfa_locked_until) ON users TO clinic_runtime")

    # Um operador não arquiva nem renomeia outro operador ativo: uma conta comprometida
    # não pode excluir a administração da plataforma inteira.
    op.execute("""
        CREATE OR REPLACE FUNCTION public.archive_platform_user(target uuid) RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public
        AS $fn$
        BEGIN
          IF NOT coalesce(public.is_platform_actor(), false)
            OR target::text = current_setting('app.user_id', true)
            OR EXISTS (SELECT 1 FROM public.platform_operators WHERE user_id = target AND active)
          THEN RETURN false; END IF;
          UPDATE public.users SET active = false, deleted_at = coalesce(deleted_at, now())
          WHERE id = target AND NOT is_service;
          IF NOT FOUND THEN RETURN false; END IF;
          UPDATE public.platform_operators SET active = false WHERE user_id = target;
          RETURN true;
        END
        $fn$
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION public.set_platform_user_login(p_user uuid, p_login text)
        RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public AS $fn$
        BEGIN
          IF NOT public.is_platform_actor() THEN RETURN false; END IF;
          IF p_user::text <> current_setting('app.user_id', true) AND EXISTS (
            SELECT 1 FROM public.platform_operators WHERE user_id = p_user AND active
          ) THEN RETURN false; END IF;
          UPDATE public.users SET login = p_login
          WHERE id = p_user AND NOT is_service AND deleted_at IS NULL;
          IF NOT FOUND THEN RETURN false; END IF;
          DELETE FROM public.mfa_challenges WHERE user_id = p_user;
          DELETE FROM public.recovery_tokens WHERE user_id = p_user;
          RETURN true;
        END
        $fn$
    """)

    # WhatsApp: a verificação das credenciais vale para a versão salva da configuração.
    op.execute("ALTER TABLE integration_configs ADD COLUMN verified_version integer")
    op.execute("ALTER TABLE integration_configs ADD COLUMN verified_at timestamptz")
    # Sinais de saúde do webhook, gravados pelo próprio endpoint (papel de runtime).
    op.execute("ALTER TABLE messaging_channels ADD COLUMN webhook_verified_at timestamptz")
    op.execute("ALTER TABLE messaging_channels ADD COLUMN last_event_at timestamptz")
    op.execute(
        "GRANT UPDATE(webhook_verified_at, last_event_at) ON messaging_channels TO clinic_runtime"
    )
    # Presença do processador de mensagens (worker sempre ligado).
    op.execute("""
        CREATE TABLE worker_heartbeats (
            name varchar(64) PRIMARY KEY,
            seen_at timestamptz NOT NULL
        )
    """)
    op.execute("REVOKE ALL ON worker_heartbeats FROM PUBLIC")
    op.execute("GRANT SELECT, INSERT, UPDATE ON worker_heartbeats TO clinic_runtime")
    # O admin da clínica ativa ou pausa o envio sem acesso administrativo ao banco.
    # Pausar é sempre permitido; ativar exige a conexão confirmada pela Meta.
    op.execute("""
        CREATE FUNCTION public.set_clinic_whatsapp_delivery(p_channel uuid, p_enabled boolean)
        RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public AS $fn$
        DECLARE
          actor_text text := current_setting('app.user_id', true);
          tenant_text text := current_setting('app.tenant_id', true);
          target public.messaging_channels%ROWTYPE;
        BEGIN
          SELECT * INTO target FROM public.messaging_channels WHERE id = p_channel FOR UPDATE;
          IF NOT FOUND OR tenant_text IS NULL OR target.tenant_id::text <> tenant_text
             OR actor_text IS NULL OR actor_text = '' OR NOT EXISTS (
               SELECT 1 FROM public.memberships m JOIN public.users u ON u.id = m.user_id
               WHERE m.user_id = actor_text::uuid AND m.tenant_id = target.tenant_id
                 AND m.role = 'admin' AND m.active AND u.active AND NOT u.is_service
                 AND m.deleted_at IS NULL AND u.deleted_at IS NULL
             )
          THEN RETURN false; END IF;
          IF p_enabled AND (
               NOT target.active OR target.graph_version IS NULL
               OR coalesce(target.webhook_verified_at, target.last_event_at) IS NULL
          ) THEN RETURN false; END IF;
          UPDATE public.messaging_channels SET send_enabled = p_enabled WHERE id = p_channel;
          RETURN true;
        END
        $fn$
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {DELIVERY_FUNCTION} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {DELIVERY_FUNCTION} TO clinic_runtime")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {DELIVERY_FUNCTION}")
    op.execute("DROP TABLE worker_heartbeats")
    op.execute(
        "REVOKE UPDATE(webhook_verified_at, last_event_at) ON messaging_channels FROM clinic_runtime"
    )
    op.execute("ALTER TABLE messaging_channels DROP COLUMN last_event_at")
    op.execute("ALTER TABLE messaging_channels DROP COLUMN webhook_verified_at")
    op.execute("ALTER TABLE integration_configs DROP COLUMN verified_at")
    op.execute("ALTER TABLE integration_configs DROP COLUMN verified_version")
    op.execute("""
        CREATE OR REPLACE FUNCTION public.set_platform_user_login(p_user uuid, p_login text)
        RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public AS $fn$
        BEGIN
          IF NOT public.is_platform_actor() THEN RETURN false; END IF;
          UPDATE public.users SET login = p_login
          WHERE id = p_user AND NOT is_service AND deleted_at IS NULL;
          IF NOT FOUND THEN RETURN false; END IF;
          DELETE FROM public.mfa_challenges WHERE user_id = p_user;
          DELETE FROM public.recovery_tokens WHERE user_id = p_user;
          RETURN true;
        END
        $fn$
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION public.archive_platform_user(target uuid) RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public
        AS $fn$
        BEGIN
          IF NOT coalesce(public.is_platform_actor(), false)
            OR target::text = current_setting('app.user_id', true)
          THEN RETURN false; END IF;
          UPDATE public.users SET active = false, deleted_at = coalesce(deleted_at, now())
          WHERE id = target AND NOT is_service;
          IF NOT FOUND THEN RETURN false; END IF;
          UPDATE public.platform_operators SET active = false WHERE user_id = target;
          RETURN true;
        END
        $fn$
    """)
    op.execute("REVOKE UPDATE(mfa_failures, mfa_locked_until) ON users FROM clinic_runtime")
    op.execute("ALTER TABLE users DROP CONSTRAINT users_mfa_failures")
    op.execute("ALTER TABLE users DROP COLUMN mfa_locked_until")
    op.execute("ALTER TABLE users DROP COLUMN mfa_failures")
