"""reconcile migrate.py drift

Revision ID: 99d2eb24405d
Revises: be7ed571ed2f
Create Date: 2026-08-20 10:49:00.000000

Databases that were brought up to the v1 schema by `migrate.py` differ from the
models in two ways. Both are artefacts of how that script had to work, not
decisions anyone made, so this revision moves the database to what the models
say.

1. Server defaults. `migrate.py` wrote `ADD COLUMN … NOT NULL DEFAULT …`
   because a NOT NULL column cannot be added to a table that already has rows
   without one. The models declare only a Python-side `default=`, so the value
   is always supplied by the ORM and the server default is redundant.

2. The Stripe unique indexes. `migrate.py` created partial indexes named
   `uq_subscriptions_stripe_*`; the models declare plain unique indexes named
   `ix_subscriptions_stripe_*`. Postgres already allows repeated NULLs in a
   unique index, so the two are equivalent in behaviour — only the name differs,
   and autogenerate would otherwise propose this swap on every future run.

Every statement is conditional, so this is a no-op against a database freshly
built by the baseline revision and a fix against one migrate.py had touched.
"""
from typing import Sequence, Union

from alembic import op

revision: str = '99d2eb24405d'
down_revision: Union[str, Sequence[str], None] = 'be7ed571ed2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column, the default migrate.py wrote) — the third item is only used to
# put the default back on downgrade.
DRIFTED_DEFAULTS: Sequence[tuple[str, str, str]] = (
    ('communities', 'status', "'active'::community_status"),
    ('communities', 'visibility', "'public'::visibility_level"),
    ('community_members', 'role', "'member'::community_role"),
    ('subscriptions', 'cancel_at_period_end', 'false'),
    ('users', 'is_staff', 'false'),
)

# (migrate.py's partial index, the model's index, the column)
DRIFTED_INDEXES: Sequence[tuple[str, str, str]] = (
    ('uq_subscriptions_stripe_customer',
     'ix_subscriptions_stripe_customer_id', 'stripe_customer_id'),
    ('uq_subscriptions_stripe_subscription',
     'ix_subscriptions_stripe_subscription_id', 'stripe_subscription_id'),
)


def upgrade() -> None:
    """Upgrade schema."""
    # DROP DEFAULT is already a no-op when there is no default to drop.
    for table, column, _default in DRIFTED_DEFAULTS:
        op.execute(f'ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT')

    for old_name, new_name, column in DRIFTED_INDEXES:
        op.execute(f'DROP INDEX IF EXISTS {old_name}')
        op.execute(
            f'CREATE UNIQUE INDEX IF NOT EXISTS {new_name} '
            f'ON subscriptions ({column})'
        )


def downgrade() -> None:
    """Downgrade schema."""
    for old_name, new_name, column in DRIFTED_INDEXES:
        op.execute(f'DROP INDEX IF EXISTS {new_name}')
        op.execute(
            f'CREATE UNIQUE INDEX IF NOT EXISTS {old_name} '
            f'ON subscriptions ({column}) WHERE {column} IS NOT NULL'
        )

    for table, column, default in DRIFTED_DEFAULTS:
        op.execute(f'ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT {default}')
