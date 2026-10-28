"""Separate approved office time and synced call time for payroll estimates.

Revision ID: 0006
Revises: 0005
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pay_profiles", sa.Column("pay_basis", sa.String(20), nullable=False, server_default="work"))
    op.add_column("pay_profiles", sa.Column("call_hourly_rate", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.alter_column("pay_profiles", "pay_basis", server_default=None)
    op.alter_column("pay_profiles", "call_hourly_rate", server_default=None)


def downgrade():
    op.drop_column("pay_profiles", "call_hourly_rate")
    op.drop_column("pay_profiles", "pay_basis")
