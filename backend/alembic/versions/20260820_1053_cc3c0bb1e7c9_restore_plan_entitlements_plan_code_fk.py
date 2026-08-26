"""restore plan_entitlements plan_code fk

Revision ID: cc3c0bb1e7c9
Revises: 99d2eb24405d
Create Date: 2026-08-20 10:53:00.000000

`PlanEntitlement.plan_code` declares a foreign key to `plans.code` with
ON DELETE CASCADE — "an entitlement row cannot outlive the plan it belongs to",
in the model's own words. Databases built before that line was added are missing
it: `create_all()` never alters a table that already exists, and migrate.py only
ever added columns and indexes, never constraints.

Conditional, so it is a no-op on a database the baseline revision built.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'cc3c0bb1e7c9'
down_revision: Union[str, Sequence[str], None] = '99d2eb24405d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The name Postgres derives for an unnamed FK, which is what the model declares.
FK_NAME = 'plan_entitlements_plan_code_fkey'


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = '{FK_NAME}'
                  AND conrelid = 'plan_entitlements'::regclass
            ) THEN
                ALTER TABLE plan_entitlements
                    ADD CONSTRAINT {FK_NAME}
                    FOREIGN KEY (plan_code) REFERENCES plans (code)
                    ON DELETE CASCADE;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(f'ALTER TABLE plan_entitlements DROP CONSTRAINT IF EXISTS {FK_NAME}')
