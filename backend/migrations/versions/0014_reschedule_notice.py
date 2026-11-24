"""Track WhatsApp notices for staff reschedules, including template-only conversations."""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE messages ADD COLUMN rescheduled_appointment_id uuid,
        ADD COLUMN template_ciphertext text,
        ADD UNIQUE (tenant_id, rescheduled_appointment_id),
        ADD FOREIGN KEY (tenant_id, rescheduled_appointment_id) REFERENCES appointments(tenant_id,id)
    """)
    op.execute("ALTER TABLE messaging_sessions ALTER COLUMN last_inbound_at DROP NOT NULL")


def downgrade() -> None:
    # A session without inbound traffic must remain outside the free-text window.
    op.execute("ALTER TABLE messaging_sessions NO FORCE ROW LEVEL SECURITY")
    op.execute(
        "UPDATE messaging_sessions SET last_inbound_at = 'epoch' WHERE last_inbound_at IS NULL"
    )
    op.execute("ALTER TABLE messaging_sessions FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE messaging_sessions ALTER COLUMN last_inbound_at SET NOT NULL")
    op.execute(
        "ALTER TABLE messages DROP COLUMN template_ciphertext, DROP COLUMN rescheduled_appointment_id"
    )
