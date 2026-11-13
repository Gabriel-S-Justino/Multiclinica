"""Allow platform operators to maintain account data."""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

LOGIN_FUNCTION = "public.set_platform_user_login(uuid,text)"


def upgrade() -> None:
    for operation in ("INSERT", "UPDATE"):
        using = "USING (public.is_platform_actor())" if operation == "UPDATE" else ""
        op.execute(f"""
            CREATE POLICY platform_profile_{operation.lower()} ON public.user_profiles
            FOR {operation} {using}
            WITH CHECK (
                public.is_platform_actor() AND EXISTS (
                    SELECT 1 FROM public.users u
                    WHERE u.id = user_profiles.user_id AND NOT u.is_service AND u.deleted_at IS NULL
                )
            )
        """)
    op.execute("""
        CREATE FUNCTION public.set_platform_user_login(p_user uuid, p_login text)
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
    op.execute(f"REVOKE ALL ON FUNCTION {LOGIN_FUNCTION} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {LOGIN_FUNCTION} TO clinic_runtime")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {LOGIN_FUNCTION}")
    op.execute("DROP POLICY platform_profile_update ON public.user_profiles")
    op.execute("DROP POLICY platform_profile_insert ON public.user_profiles")
