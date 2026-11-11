"""Record when a lead last enquired through a capture channel and when the team first responded.

Revision ID: 0010
Revises: 0009
"""

from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("enquiry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("leads", sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_lead_org_enquiry", "leads", ["org_id", "enquiry_at"])


def downgrade():
    if (
        op.get_bind()
        .execute(
            sa.text("SELECT EXISTS(SELECT 1 FROM leads WHERE enquiry_at IS NOT NULL OR first_response_at IS NOT NULL)")
        )
        .scalar()
    ):
        raise RuntimeError(
            "Cannot downgrade 0010 while enquiry or first-response times exist; retain the schema or restore a backup"
        )
    op.drop_index("ix_lead_org_enquiry", table_name="leads")
    op.drop_column("leads", "first_response_at")
    op.drop_column("leads", "enquiry_at")
