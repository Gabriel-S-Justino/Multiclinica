"""Separate the global console from clinic records."""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("tenants", "users", "memberships"):
        op.execute(f"ALTER TABLE {table} ADD COLUMN deleted_at timestamptz")
    op.execute("ALTER TABLE tenants ADD COLUMN internal boolean NOT NULL DEFAULT false")
    op.execute("GRANT UPDATE(deleted_at) ON tenants, memberships TO clinic_runtime")
    op.execute("ALTER TABLE platform_audit_logs ALTER COLUMN tenant_id DROP NOT NULL")
    op.execute("""
        CREATE TABLE platform_operations (
            key varchar(128) PRIMARY KEY,
            actor_id uuid NOT NULL REFERENCES users(id),
            operation varchar(30) NOT NULL,
            request_hash varchar(64) NOT NULL,
            result jsonb NOT NULL
        )
    """)
    op.execute("GRANT SELECT, INSERT ON platform_operations TO clinic_runtime")
    op.execute("ALTER TABLE platform_operations ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE OR REPLACE FUNCTION public.is_platform_actor() RETURNS boolean
        LANGUAGE sql STABLE SET search_path = pg_catalog, public
        AS $fn$
          SELECT coalesce(current_setting('app.platform', true) = 'true', false) AND EXISTS (
            SELECT 1 FROM public.platform_operators p JOIN public.users u ON u.id = p.user_id
            WHERE p.active AND u.active AND u.deleted_at IS NULL
              AND p.user_id::text = current_setting('app.user_id', true)
          )
        $fn$
    """)
    op.execute("""
        CREATE FUNCTION public.archive_platform_user(target uuid) RETURNS boolean
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
    op.execute("REVOKE ALL ON FUNCTION public.archive_platform_user(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.archive_platform_user(uuid) TO clinic_runtime")
    op.execute("""
        CREATE POLICY platform_audit_read ON audit_logs FOR SELECT
        USING (public.is_platform_actor())
    """)
    op.execute("""
        CREATE POLICY platform_operations_access ON platform_operations
        USING (public.is_platform_actor()) WITH CHECK (public.is_platform_actor())
    """)
    op.execute("""
        CREATE POLICY platform_membership_read ON memberships FOR SELECT
        USING (public.is_platform_actor())
    """)
    op.execute("CREATE INDEX platform_audit_date ON platform_audit_logs(created_at, id)")
    op.execute("CREATE INDEX clinic_audit_date ON audit_logs(created_at, id)")


def downgrade() -> None:
    op.execute("DROP INDEX clinic_audit_date")
    op.execute("DROP INDEX platform_audit_date")
    op.execute("DROP POLICY platform_audit_read ON audit_logs")
    op.execute("DROP POLICY platform_membership_read ON memberships")
    op.execute("DROP FUNCTION public.archive_platform_user(uuid)")
    op.execute("DROP TABLE platform_operations")
    op.execute("""
        CREATE OR REPLACE FUNCTION public.is_platform_actor() RETURNS boolean
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
    op.execute("""
        DO $fn$ BEGIN
          IF EXISTS (SELECT 1 FROM platform_audit_logs WHERE tenant_id IS NULL) THEN
            RAISE EXCEPTION 'Existem eventos globais. Use uma versão compatível com o esquema 0009.';
          END IF;
        END $fn$
    """)
    op.execute("ALTER TABLE platform_audit_logs ALTER COLUMN tenant_id SET NOT NULL")
    op.execute("ALTER TABLE tenants DROP COLUMN internal")
    for table in ("tenants", "users", "memberships"):
        op.execute(f"ALTER TABLE {table} DROP COLUMN deleted_at")
