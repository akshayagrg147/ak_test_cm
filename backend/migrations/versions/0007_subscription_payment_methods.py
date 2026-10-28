"""Add cash collection alongside existing UPI subscription payments.

Revision ID: 0007
Revises: 0006
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("platform_billing", sa.Column("upi_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("platform_billing", sa.Column("cod_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("platform_billing", sa.Column("cod_instructions", sa.String(2000), nullable=False, server_default=""))
    op.add_column(
        "subscription_payments", sa.Column("payment_method", sa.String(10), nullable=False, server_default="upi")
    )
    op.alter_column("subscription_payments", "reference", existing_type=sa.String(80), nullable=True)
    op.create_check_constraint(
        "ck_subscription_payment_method", "subscription_payments", "payment_method IN ('upi', 'cod')"
    )
    op.create_check_constraint(
        "ck_subscription_payment_reference",
        "subscription_payments",
        "(payment_method = 'upi' AND reference IS NOT NULL) OR (payment_method = 'cod' AND reference IS NULL)",
    )
    for name in ["upi_enabled", "cod_enabled", "cod_instructions"]:
        op.alter_column("platform_billing", name, server_default=None)
    op.alter_column("subscription_payments", "payment_method", server_default=None)


def downgrade():
    if op.get_bind().scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM subscription_payments WHERE payment_method = 'cod')")
    ):
        raise RuntimeError(
            "Keep migration 0007: cash payment history cannot be represented by the older UPI-only schema"
        )
    op.drop_constraint("ck_subscription_payment_reference", "subscription_payments", type_="check")
    op.drop_constraint("ck_subscription_payment_method", "subscription_payments", type_="check")
    op.alter_column("subscription_payments", "reference", existing_type=sa.String(80), nullable=False)
    op.drop_column("subscription_payments", "payment_method")
    for name in ["cod_instructions", "cod_enabled", "upi_enabled"]:
        op.drop_column("platform_billing", name)
