"""Retire unchanged healthcare defaults in existing real estate companies.

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE definitions AS d
        SET active = false
        FROM organizations AS o
        WHERE d.org_id = o.id
          AND o.settings->>'industry' = 'real_estate'
          AND d.kind = 'category'
          AND d.key IN ('pharmaceutical', 'ayurvedic', 'homeopathic', 'nutraceutical', 'generic')
          AND lower(d.label) = d.key
    """)
    op.execute("""
        UPDATE organizations
        SET settings = (settings::jsonb || '{"pharma_enabled": false}'::jsonb)::json
        WHERE settings->>'industry' = 'real_estate'
    """)


def downgrade():
    # This data correction is retained on schema downgrade. Reactivating categories
    # would restore the defect and could override later administrator choices.
    # Definitions, customer category values and saved filters were never removed.
    pass
