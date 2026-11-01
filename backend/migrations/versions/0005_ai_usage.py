"""Conservative atomic AI usage reservations; no provider enabled."""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

DDL = [
    "\nCREATE TABLE ai_usage (\n\trequest_key VARCHAR(128) NOT NULL, \n\tconversation_key VARCHAR(64) NOT NULL, \n\tperiod VARCHAR(7) NOT NULL, \n\tprovider VARCHAR(80) NOT NULL, \n\tmodel VARCHAR(120) NOT NULL, \n\treserved_tokens INTEGER NOT NULL, \n\tused_tokens INTEGER NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tUNIQUE (tenant_id, request_key), \n\tCHECK (reserved_tokens > 0 AND used_tokens >= 0 AND used_tokens <= reserved_tokens), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_ai_usage_tenant_id ON ai_usage (tenant_id)",
]


def upgrade() -> None:
    for statement in DDL:
        op.execute(statement)
    op.execute("REVOKE ALL ON ai_usage FROM PUBLIC")
    op.execute("ALTER TABLE ai_usage ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ai_usage FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON ai_usage USING (tenant_id::text=current_setting('app.tenant_id',true)) WITH CHECK (tenant_id::text=current_setting('app.tenant_id',true))"
    )
    op.execute("GRANT SELECT,INSERT ON ai_usage TO clinic_runtime")
    op.execute("GRANT UPDATE(used_tokens,status) ON ai_usage TO clinic_runtime")


def downgrade() -> None:
    op.execute("DROP TABLE ai_usage")
