"""Portal administration, inbox, invitation consent and exceptional read grants."""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TABLES = [
    "admin_notifications",
    "break_glass_requests",
    "clinic_policies",
    "entity_versions",
    "integration_configs",
    "invitations",
    "platform_audit_logs",
    "platform_operators",
    "service_queues",
    "queue_memberships",
    "handoffs",
    "messages",
]
DDL = [
    "\nCREATE TABLE admin_notifications (\n\tnotification_type VARCHAR(60) NOT NULL, \n\tresource_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_admin_notifications_tenant_id ON admin_notifications (tenant_id)",
    "\nCREATE TABLE break_glass_requests (\n\trequester_user_id UUID NOT NULL, \n\tappointment_id UUID NOT NULL, \n\treason_ciphertext VARCHAR(4096) NOT NULL, \n\tduration_minutes INTEGER NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE, \n\tapproved_by_user_id UUID, \n\tversion INTEGER NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tCHECK (duration_minutes BETWEEN 1 AND 15), \n\tCHECK (status IN ('pending','approved','rejected','revoked')), \n\tFOREIGN KEY(requester_user_id) REFERENCES users (id), \n\tFOREIGN KEY(approved_by_user_id) REFERENCES users (id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_break_glass_requests_tenant_id ON break_glass_requests (tenant_id)",
    "\nCREATE TABLE clinic_policies (\n\tidentity_policy_approved BOOLEAN NOT NULL, \n\tidentity_policy_reference VARCHAR(80) NOT NULL, \n\tverification_ttl_minutes INTEGER NOT NULL, \n\tversion INTEGER NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tUNIQUE (tenant_id), \n\tCHECK (verification_ttl_minutes BETWEEN 1 AND 10080), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_clinic_policies_tenant_id ON clinic_policies (tenant_id)",
    "\nCREATE TABLE entity_versions (\n\tentity_type VARCHAR(40) NOT NULL, \n\tentity_id UUID NOT NULL, \n\tversion INTEGER NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tUNIQUE (tenant_id, entity_type, entity_id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_entity_versions_tenant_id ON entity_versions (tenant_id)",
    "\nCREATE TABLE integration_configs (\n\tprovider VARCHAR(30) NOT NULL, \n\tcredentials_ciphertext VARCHAR(32768) NOT NULL, \n\tversion INTEGER NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tUNIQUE (tenant_id, provider), \n\tCHECK (provider IN ('whatsapp','ai')), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_integration_configs_tenant_id ON integration_configs (tenant_id)",
    "\nCREATE TABLE invitations (\n\trecipient_hash VARCHAR(64) NOT NULL, \n\tlogin_ciphertext VARCHAR(2048) NOT NULL, \n\trole VARCHAR(30) NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tCHECK (role IN ('collaborator','reception','admin')), \n\tCHECK (status IN ('pending','accepted','revoked')), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_invitations_tenant_id ON invitations (tenant_id)",
    "CREATE INDEX ix_invitations_recipient_hash ON invitations (recipient_hash)",
    "\nCREATE TABLE platform_audit_logs (\n\tid UUID NOT NULL, \n\tactor_id UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\taction VARCHAR(80) NOT NULL, \n\tresource_id UUID, \n\tcorrelation_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(actor_id) REFERENCES users (id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "\nCREATE TABLE platform_operators (\n\tuser_id UUID NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tPRIMARY KEY (user_id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)\n\n",
    "\nCREATE TABLE service_queues (\n\tname VARCHAR(120) NOT NULL, \n\tkind VARCHAR(30) NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\thours JSONB NOT NULL, \n\toutside_hours_notice VARCHAR(300) NOT NULL, \n\tversion INTEGER NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_service_queues_tenant_id ON service_queues (tenant_id)",
    "\nCREATE TABLE queue_memberships (\n\tqueue_id UUID NOT NULL, \n\tmembership_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tUNIQUE (tenant_id, queue_id, membership_id), \n\tFOREIGN KEY(tenant_id, queue_id) REFERENCES service_queues (tenant_id, id), \n\tFOREIGN KEY(tenant_id, membership_id) REFERENCES memberships (tenant_id, id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_queue_memberships_tenant_id ON queue_memberships (tenant_id)",
    "\nCREATE TABLE handoffs (\n\tconversation_id UUID NOT NULL, \n\tqueue_id UUID NOT NULL, \n\treason_code VARCHAR(40) NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tassignee_membership_id UUID, \n\tversion INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tFOREIGN KEY(tenant_id, conversation_id) REFERENCES conversations (tenant_id, id), \n\tFOREIGN KEY(tenant_id, queue_id) REFERENCES service_queues (tenant_id, id), \n\tFOREIGN KEY(tenant_id, assignee_membership_id) REFERENCES memberships (tenant_id, id), \n\tCHECK (status IN ('waiting','assigned','released','closed')), \n\tCHECK (version >= 0), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_handoffs_tenant_id ON handoffs (tenant_id)",
    "CREATE UNIQUE INDEX handoff_one_open ON handoffs (tenant_id, conversation_id) WHERE status IN ('waiting','assigned')",
    "\nCREATE TABLE messages (\n\tconversation_id UUID NOT NULL, \n\tbody_ciphertext TEXT NOT NULL, \n\tdirection VARCHAR(20) NOT NULL, \n\tdelivery_status VARCHAR(20) NOT NULL, \n\tsender_user_id UUID, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tid UUID NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tenant_id, id), \n\tFOREIGN KEY(tenant_id, conversation_id) REFERENCES conversations (tenant_id, id), \n\tCHECK (direction IN ('inbound','outbound')), \n\tFOREIGN KEY(sender_user_id) REFERENCES users (id), \n\tFOREIGN KEY(tenant_id) REFERENCES tenants (id)\n)\n\n",
    "CREATE INDEX ix_messages_tenant_id ON messages (tenant_id)",
    "CREATE INDEX messages_conversation_page ON messages (tenant_id, conversation_id, created_at, id)",
]

CONFIG_TABLES = [
    "services",
    "professional_services",
    "service_resources",
    "professional_schedules",
    "schedule_exceptions",
    "blocked_periods",
    "holidays",
    "professionals",
    "units",
    "resources",
]


def upgrade() -> None:
    op.execute("ALTER TABLE tenants ADD COLUMN version integer NOT NULL DEFAULT 0")
    op.execute(
        "ALTER TABLE memberships ADD COLUMN can_manage_schedule boolean NOT NULL DEFAULT false"
    )
    op.execute("ALTER TABLE services ADD COLUMN display_order integer NOT NULL DEFAULT 0")
    op.execute(
        "ALTER TABLE audit_logs ADD COLUMN correlation_id uuid NOT NULL DEFAULT gen_random_uuid()"
    )
    op.execute("ALTER TABLE contact_patient_links ADD COLUMN verification_reference varchar(80)")
    op.execute("ALTER TABLE memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memberships FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY memberships_access ON memberships USING (tenant_id::text=current_setting('app.tenant_id',true) OR user_id::text=current_setting('app.user_id',true)) WITH CHECK (tenant_id::text=current_setting('app.tenant_id',true))"
    )
    for statement in DDL:
        op.execute(statement)
    op.execute("ALTER TABLE services ADD COLUMN service_queue_id uuid")
    op.execute(
        "ALTER TABLE services ADD CONSTRAINT services_queue_fk FOREIGN KEY(tenant_id,service_queue_id) REFERENCES service_queues(tenant_id,id)"
    )
    for table in TABLES:
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC")
        op.execute(f"GRANT SELECT ON {table} TO clinic_runtime")
        if table in {"platform_operators", "platform_audit_logs"}:
            continue
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        condition = "tenant_id::text=current_setting('app.tenant_id',true)"
        visibility = condition
        if table == "break_glass_requests":
            visibility = (
                f"({condition} OR requester_user_id::text=current_setting('app.user_id',true))"
            )
        elif table == "invitations":
            visibility = (
                f"({condition} OR recipient_hash=current_setting('app.invite_recipient',true))"
            )
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} USING ({visibility}) WITH CHECK ({condition})"
        )
        op.execute(f"GRANT INSERT ON {table} TO clinic_runtime")
        if table not in {"admin_notifications", "messages", "invitations", "break_glass_requests"}:
            op.execute(f"GRANT UPDATE ON {table} TO clinic_runtime")
    op.execute("GRANT INSERT ON platform_audit_logs TO clinic_runtime")
    op.execute("GRANT UPDATE(status) ON invitations TO clinic_runtime")
    op.execute(
        "GRANT UPDATE(status,expires_at,approved_by_user_id,version) ON break_glass_requests TO clinic_runtime"
    )
    op.execute("GRANT DELETE ON queue_memberships TO clinic_runtime")
    for table in CONFIG_TABLES:
        op.execute(f"GRANT INSERT, UPDATE ON {table} TO clinic_runtime")
    for table in [
        "professional_schedules",
        "schedule_exceptions",
        "blocked_periods",
        "holidays",
        "service_resources",
        "professional_assignments",
    ]:
        op.execute(f"GRANT DELETE ON {table} TO clinic_runtime")
    op.execute("GRANT INSERT ON professional_assignments, memberships, tenants TO clinic_runtime")
    op.execute("GRANT UPDATE(role,active,can_manage_schedule) ON memberships TO clinic_runtime")
    op.execute("GRANT UPDATE(name,timezone,active,version) ON tenants TO clinic_runtime")
    op.execute("GRANT UPDATE ON contact_patient_links TO clinic_runtime")


def downgrade() -> None:
    op.execute("ALTER TABLE services DROP COLUMN service_queue_id")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    for table in CONFIG_TABLES:
        op.execute(f"REVOKE INSERT, UPDATE, DELETE ON {table} FROM clinic_runtime")
    op.execute(
        "REVOKE INSERT, UPDATE, DELETE ON professional_assignments, memberships, tenants FROM clinic_runtime"
    )
    op.execute("REVOKE UPDATE ON contact_patient_links FROM clinic_runtime")
    op.execute("ALTER TABLE contact_patient_links DROP COLUMN verification_reference")
    op.execute("ALTER TABLE audit_logs DROP COLUMN correlation_id")
    op.execute("ALTER TABLE services DROP COLUMN display_order")
    op.execute("ALTER TABLE memberships DROP COLUMN can_manage_schedule")
    op.execute("ALTER TABLE tenants DROP COLUMN version")
    op.execute("DROP POLICY memberships_access ON memberships")
    op.execute("ALTER TABLE memberships NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memberships DISABLE ROW LEVEL SECURITY")
