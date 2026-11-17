"""Public property share links and their privacy-safe view counts.

Revision ID: 0012
Revises: 0011
"""

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "property_shares",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("property_id", sa.String(36), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("token_enc", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("photo_file_ids", sa.JSON(), nullable=True),
        sa.Column("doc_file_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("show_rera", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("contact_mode", sa.String(20), nullable=False, server_default="sharer"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("contact_mode IN ('sharer', 'company')", name="ck_property_share_contact"),
    )
    op.create_index("ix_property_shares_org_id", "property_shares", ["org_id"])
    op.create_index("ix_property_shares_property_id", "property_shares", ["property_id"])
    op.create_index(
        "uq_active_property_share", "property_shares", ["property_id"], unique=True,
        postgresql_where=sa.text("enabled = true"),
    )
    op.create_table(
        "property_share_views",
        sa.Column("share_id", sa.String(36), sa.ForeignKey("property_shares.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("visitor", sa.String(64), primary_key=True),
    )


def downgrade():
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM property_shares)")).scalar():
        raise RuntimeError("Refusing to drop property_shares while share links exist; turn them off and remove them first")
    op.drop_table("property_share_views")
    op.drop_index("uq_active_property_share", table_name="property_shares")
    op.drop_index("ix_property_shares_property_id", table_name="property_shares")
    op.drop_index("ix_property_shares_org_id", table_name="property_shares")
    op.drop_table("property_shares")
