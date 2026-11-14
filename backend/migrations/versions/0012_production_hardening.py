"""Production hardening: MFA lockout and protection between platform operators."""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

ARCHIVE_FUNCTION = "public.archive_platform_user(uuid)"
LOGIN_FUNCTION = "public.set_platform_user_login(uuid,text)"


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


def downgrade() -> None:
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
