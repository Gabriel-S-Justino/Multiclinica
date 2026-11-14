"""Let a person replace their authenticator with a one-time code issued by the team."""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

SIGNATURE = "public.reset_user_authenticator(uuid,text,text,integer)"


def upgrade() -> None:
    # O papel de runtime não altera mfa_secret diretamente. A troca só acontece com um
    # código de reconfiguração válido, que é consumido na mesma operação.
    op.execute("""
    CREATE FUNCTION public.reset_user_authenticator(
        p_user uuid, p_token_hash text, p_mfa_secret text, p_totp_step integer
    ) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog, public
    AS $function$
    BEGIN
        IF length(p_mfa_secret) NOT BETWEEN 1 AND 512 OR p_totp_step < 0 THEN
            RETURN false;
        END IF;
        DELETE FROM public.recovery_tokens
        WHERE token_hash = p_token_hash AND user_id = p_user AND expires_at > clock_timestamp();
        IF NOT FOUND THEN
            RETURN false;
        END IF;
        UPDATE public.users
        SET mfa_secret = p_mfa_secret, last_totp_step = p_totp_step,
            mfa_failures = 0, mfa_locked_until = NULL
        WHERE id = p_user AND active AND NOT is_service AND deleted_at IS NULL;
        RETURN FOUND;
    END
    $function$;
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO clinic_runtime")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {SIGNATURE}")
