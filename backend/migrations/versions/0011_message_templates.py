"""Company message templates for WhatsApp click-to-chat and SMS links.

Revision ID: 0011
Revises: 0010
"""

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "message_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False, server_default="any"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_message_templates_org_id", "message_templates", ["org_id"])
    op.create_index(
        "uq_message_template_name",
        "message_templates",
        ["org_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("deleted = false"),
    )


def downgrade():
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM message_templates)")).scalar():
        raise RuntimeError(
            "Refusing to drop message_templates while companies have templates; export or remove them first"
        )
    op.drop_index("uq_message_template_name", table_name="message_templates")
    op.drop_index("ix_message_templates_org_id", table_name="message_templates")
    op.drop_table("message_templates")
