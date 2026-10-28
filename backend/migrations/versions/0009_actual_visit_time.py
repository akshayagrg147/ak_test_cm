"""Retain actual early attendance separately from the agreed visit schedule.

Revision ID: 0009
Revises: 0008
"""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("site_visits", sa.Column("actual_started_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT EXISTS(SELECT 1 FROM site_visits WHERE actual_started_at IS NOT NULL)"))
        .scalar()
    ):
        raise RuntimeError(
            "Cannot downgrade 0009 while actual visit times exist; retain the schema or restore a matched backup"
        )
    op.drop_column("site_visits", "actual_started_at")
