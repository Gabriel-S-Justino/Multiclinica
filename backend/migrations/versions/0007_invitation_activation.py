"""Allow the portal to create a user for a valid, pending invitation."""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

SIGNATURE = "public.activate_invited_user(uuid,text,text,text,text,integer)"


def upgrade() -> None:
    op.execute("""
    CREATE FUNCTION public.activate_invited_user(
        p_invitation uuid, p_login text, p_recipient text,
        p_password_hash text, p_mfa_secret text, p_totp_step integer
    ) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog, public
    AS $function$
    DECLARE
        new_user uuid;
    BEGIN
        IF length(p_login) NOT BETWEEN 3 AND 254
           OR p_login <> lower(btrim(p_login))
           OR p_recipient IS DISTINCT FROM current_setting('app.invite_recipient', true)
           OR p_password_hash NOT LIKE '$argon2id$%'
           OR length(p_mfa_secret) NOT BETWEEN 1 AND 512
           OR p_totp_step < 0
           OR NOT EXISTS (
               SELECT 1 FROM public.invitations i
               JOIN public.tenants t ON t.id = i.tenant_id
               WHERE i.id = p_invitation AND i.recipient_hash = p_recipient
                 AND i.tenant_id::text = current_setting('app.tenant_id', true)
                 AND i.status = 'pending' AND i.expires_at > clock_timestamp()
                 AND t.active
           )
        THEN
            RETURN NULL;
        END IF;
        INSERT INTO public.users (id, login, password_hash, active, mfa_secret, last_totp_step)
        VALUES (gen_random_uuid(), p_login, p_password_hash, true, p_mfa_secret, p_totp_step)
        ON CONFLICT (login) DO NOTHING
        RETURNING id INTO new_user;
        RETURN new_user;
    END
    $function$;
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO clinic_runtime")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {SIGNATURE}")
