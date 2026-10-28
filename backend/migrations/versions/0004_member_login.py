"""Audited administrator login as a company member.

Revision ID: 0004
Revises: 34994cab372e
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "34994cab372e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("auth_sessions", sa.Column("acting_user_id", sa.String(36), nullable=True))
    op.add_column("auth_sessions", sa.Column("acting_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("auth_sessions", sa.Column("parent_session_id", sa.String(36), nullable=True))
    op.create_foreign_key("auth_sessions_acting_user_id_fkey", "auth_sessions", "users", ["acting_user_id"], ["id"])
    op.create_foreign_key("auth_sessions_parent_session_id_fkey", "auth_sessions", "auth_sessions", ["parent_session_id"], ["id"])
    op.create_index("ix_auth_sessions_acting_user_id", "auth_sessions", ["acting_user_id"])


def downgrade():
    op.drop_index("ix_auth_sessions_acting_user_id", table_name="auth_sessions")
    op.drop_constraint("auth_sessions_parent_session_id_fkey", "auth_sessions", type_="foreignkey")
    op.drop_constraint("auth_sessions_acting_user_id_fkey", "auth_sessions", type_="foreignkey")
    op.drop_column("auth_sessions", "parent_session_id")
    op.drop_column("auth_sessions", "acting_until")
    op.drop_column("auth_sessions", "acting_user_id")
