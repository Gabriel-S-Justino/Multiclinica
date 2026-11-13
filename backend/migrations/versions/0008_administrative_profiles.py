"""Store administrative registration and self-service profiles."""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tenants ADD COLUMN registration jsonb")
    op.execute("GRANT UPDATE(registration) ON tenants TO clinic_runtime")
    op.execute("""
    CREATE FUNCTION public.is_platform_actor() RETURNS boolean
    LANGUAGE sql STABLE SET search_path = pg_catalog, public
    AS $fn$
      SELECT EXISTS (
        SELECT 1 FROM public.platform_operators p
        JOIN public.users u ON u.id = p.user_id
        JOIN public.memberships m ON m.user_id = p.user_id
        JOIN public.tenants t ON t.id = m.tenant_id
        WHERE p.active AND u.active AND m.active AND t.active AND m.role = 'superadmin'
          AND p.user_id::text = current_setting('app.user_id', true)
          AND m.tenant_id::text = current_setting('app.tenant_id', true)
      )
    $fn$
    """)
    op.execute("REVOKE ALL ON FUNCTION public.is_platform_actor() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.is_platform_actor() TO clinic_runtime")
    op.execute("""
    CREATE TABLE public.user_profiles (
      user_id uuid PRIMARY KEY REFERENCES public.users(id),
      details jsonb,
      photo bytea CHECK (octet_length(photo) <= 45000)
    )
    """)
    op.execute("ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_profiles FORCE ROW LEVEL SECURITY")
    op.execute("""
    CREATE POLICY own_profile ON user_profiles
      USING (user_id::text = current_setting('app.user_id', true))
      WITH CHECK (user_id::text = current_setting('app.user_id', true))
    """)
    op.execute("""
    CREATE POLICY platform_profile_read ON user_profiles FOR SELECT
      USING (public.is_platform_actor())
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE ON user_profiles TO clinic_runtime")
    op.execute("""
    CREATE FUNCTION public.set_platform_user_active(p_user uuid, p_active boolean)
    RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog, public
    AS $fn$
    BEGIN
      IF NOT public.is_platform_actor()
        OR p_user::text = current_setting('app.user_id', true)
        OR EXISTS (SELECT 1 FROM public.platform_operators WHERE user_id = p_user AND active)
      THEN
        RETURN false;
      END IF;
      UPDATE public.users SET active = p_active WHERE id = p_user AND NOT is_service;
      RETURN FOUND;
    END
    $fn$
    """)
    op.execute("REVOKE ALL ON FUNCTION public.set_platform_user_active(uuid,boolean) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.set_platform_user_active(uuid,boolean) TO clinic_runtime"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION public.set_platform_user_active(uuid,boolean)")
    op.execute("DROP TABLE public.user_profiles")
    op.execute("DROP FUNCTION public.is_platform_actor()")
    op.execute("ALTER TABLE tenants DROP COLUMN registration")
