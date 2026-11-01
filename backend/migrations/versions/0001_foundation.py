"""Create identity, authorization, audit and tenant isolation foundation."""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "units",
    "resources",
    "users",
    "tenants",
    "memberships",
    "professionals",
    "professional_assignments",
    "portal_sessions",
    "mfa_challenges",
    "recovery_tokens",
    "rate_limit_buckets",
    "audit_logs",
]

DDL = [
    '\nCREATE TABLE rate_limit_buckets (\n\tkey VARCHAR(64) NOT NULL, \n\t"window" INTEGER NOT NULL, \n\tcount INTEGER NOT NULL, \n\tPRIMARY KEY (key, "window")\n)\n\n',
    "\nCREATE TABLE tenants (\n\tid UUID NOT NULL, \n\tname VARCHAR(120) NOT NULL, \n\ttimezone VARCHAR(64) NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tPRIMARY KEY (id)\n)\n\n",
    "\nCREATE TABLE users (\n\tid UUID NOT NULL, \n\tlogin VARCHAR(254) NOT NULL, \n\tpassword_hash VARCHAR(512) NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tmfa_secret VARCHAR(512), \n\tlast_totp_step INTEGER NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (login)\n)\n\n",
    "\nCREATE TABLE audit_logs (\n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tactor_id UUID NOT NULL, \n\taction VARCHAR(80) NOT NULL, \n\tresource_id UUID, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id), \n\tFOREIGN KEY(actor_id) REFERENCES users (id)\n)\n\n",
    "CREATE INDEX ix_audit_logs_tenant_id ON audit_logs (tenant_id)",
    "\nCREATE TABLE memberships (\n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tuser_id UUID NOT NULL, \n\trole VARCHAR(30) NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tUNIQUE (tenant_id, user_id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)\n\n",
    "CREATE INDEX ix_memberships_tenant_id ON memberships (tenant_id)",
    "\nCREATE TABLE mfa_challenges (\n\ttoken_hash VARCHAR(64) NOT NULL, \n\tuser_id UUID NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (token_hash), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)\n\n",
    "\nCREATE TABLE professionals (\n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tuser_id UUID, \n\tdisplay_name VARCHAR(120) NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)\n\n",
    "CREATE INDEX ix_professionals_tenant_id ON professionals (tenant_id)",
    "\nCREATE TABLE recovery_tokens (\n\ttoken_hash VARCHAR(64) NOT NULL, \n\tuser_id UUID NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (token_hash), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)\n\n",
    "\nCREATE TABLE units (\n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tname VARCHAR(120) NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_units_tenant_id ON units (tenant_id)",
    "\nCREATE TABLE portal_sessions (\n\ttoken_hash VARCHAR(64) NOT NULL, \n\tuser_id UUID NOT NULL, \n\tmembership_id UUID, \n\tcsrf_hash VARCHAR(64) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tidle_expires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tauthenticated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tmfa_verified BOOLEAN NOT NULL, \n\tPRIMARY KEY (token_hash), \n\tFOREIGN KEY(user_id) REFERENCES users (id), \n\tFOREIGN KEY(membership_id) REFERENCES memberships (id)\n)\n\n",
    "\nCREATE TABLE professional_assignments (\n\ttenant_id UUID NOT NULL, \n\tmembership_id UUID NOT NULL, \n\tprofessional_id UUID NOT NULL, \n\tPRIMARY KEY (tenant_id, membership_id, professional_id), \n\tFOREIGN KEY(tenant_id, membership_id) REFERENCES memberships (tenant_id, id), \n\tFOREIGN KEY(tenant_id, professional_id) REFERENCES professionals (tenant_id, id)\n)\n\n",
    "\nCREATE TABLE resources (\n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tunit_id UUID NOT NULL, \n\tname VARCHAR(120) NOT NULL, \n\tcapacity INTEGER NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT resource_unit_capacity CHECK (capacity = 1), \n\tUNIQUE (tenant_id, id), \n\tFOREIGN KEY(tenant_id, unit_id) REFERENCES units (tenant_id, id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_resources_tenant_id ON resources (tenant_id)",
]


def upgrade() -> None:
    for statement in DDL:
        op.execute(statement)
    op.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    op.execute(
        "ALTER TABLE memberships ADD CONSTRAINT membership_role CHECK (role IN ('collaborator','reception','admin','superadmin'))"
    )
    for name in ("units", "resources", "professionals", "professional_assignments", "audit_logs"):
        # Only static, source-controlled identifiers are interpolated.
        op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {name} USING (tenant_id::text = current_setting('app.tenant_id', true)) WITH CHECK (tenant_id::text = current_setting('app.tenant_id', true))"
        )
    op.execute("GRANT USAGE ON SCHEMA public TO clinic_runtime")
    for name in TABLES:
        op.execute(f"REVOKE ALL ON {name} FROM PUBLIC")
        if name == "audit_logs":
            op.execute(f"GRANT SELECT, INSERT ON {name} TO clinic_runtime")
        else:
            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {name} TO clinic_runtime")
    # Runtime cannot change identities, roles, professionals or tenant assignments.
    for name in (
        "units",
        "resources",
        "tenants",
        "memberships",
        "professionals",
        "professional_assignments",
    ):
        op.execute(f"REVOKE INSERT, UPDATE, DELETE ON {name} FROM clinic_runtime")
    op.execute("REVOKE INSERT, DELETE ON users FROM clinic_runtime")
    op.execute("REVOKE UPDATE ON users FROM clinic_runtime")
    op.execute("GRANT UPDATE(password_hash, last_totp_step) ON users TO clinic_runtime")


def downgrade() -> None:
    op.execute("DROP TABLE resources")
    op.execute("DROP TABLE professional_assignments")
    op.execute("DROP TABLE portal_sessions")
    op.execute("DROP TABLE units")
    op.execute("DROP TABLE recovery_tokens")
    op.execute("DROP TABLE professionals")
    op.execute("DROP TABLE mfa_challenges")
    op.execute("DROP TABLE memberships")
    op.execute("DROP TABLE audit_logs")
    op.execute("DROP TABLE users")
    op.execute("DROP TABLE tenants")
    op.execute("DROP TABLE rate_limit_buckets")
