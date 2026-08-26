"""plan display names: Freemium, Silver, Gold

Revision ID: c93a5f7e21d8
Revises: b7e2d4a91c36
Create Date: 2026-08-21 12:00:00.000000

Renames only `plans.name`, which is the string the pricing page and the upgrade
prompts show. The `plan_tier` enum codes — `early_access`, `member`,
`professional` — are what Stripe, every API contract and the SPA key on, and are
deliberately left alone. The pairing is fixed by price and is exact:

    Freemium = early_access   $0
    Silver   = member         $25/mo
    Gold     = professional   $100/mo

Guarded on the old value, so a name someone has since tuned in the database is
not overwritten.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'c93a5f7e21d8'
down_revision: Union[str, Sequence[str], None] = 'b7e2d4a91c36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RENAMES = (
    ('early_access', 'Early access', 'Freemium'),
    ('member', 'Member', 'Silver'),
    ('professional', 'Professional', 'Gold'),
)


def _rename(pairs) -> None:
    for code, before, after in pairs:
        op.execute(
            "UPDATE plans SET name = '%s' WHERE code = '%s' AND name = '%s'"
            % (after, code, before)
        )


def upgrade() -> None:
    """Upgrade schema."""
    _rename(RENAMES)


def downgrade() -> None:
    """Downgrade schema."""
    _rename([(code, after, before) for code, before, after in RENAMES])
