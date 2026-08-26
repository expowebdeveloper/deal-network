"""silver and gold community ceilings

Revision ID: b7e2d4a91c36
Revises: a4f1c8d2e5b7
Create Date: 2026-08-21 11:30:00.000000

The product's tier table, applied to the seeded catalogue:

    Freemium (early_access)   0 communities   0 moderator seats
    Silver   (member)         1 community     0 moderator seats
    Gold     (professional)   3 communities   3 moderator seats

Previously Silver allowed 10 communities and 2 moderators, and Gold was
unlimited with 10 moderators. `plan_entitlements` is what a seeded database
actually reads — the matrices in `services/entitlements.py` are only the
fallback for an unseeded one — so both have to move or a deployed environment
keeps the old ceilings.

`is_unlimited` is cleared on Gold's `community.max_owned`: it was the one row
that stored "no limit" rather than a number.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b7e2d4a91c36'
down_revision: Union[str, Sequence[str], None] = 'a4f1c8d2e5b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: (plan_code, key, limit_value) for the new ceilings and the old ones.
NEW = (
    ('member', 'community.max_owned', 1),
    ('member', 'community.max_moderators', 0),
    ('professional', 'community.max_owned', 3),
    ('professional', 'community.max_moderators', 3),
)
OLD = (
    ('member', 'community.max_owned', 10),
    ('member', 'community.max_moderators', 2),
    ('professional', 'community.max_owned', None),   # was unlimited
    ('professional', 'community.max_moderators', 10),
)


def _apply(rows) -> None:
    for plan_code, key, value in rows:
        if value is None:
            op.execute(
                "UPDATE plan_entitlements "
                "SET limit_value = NULL, is_unlimited = true "
                f"WHERE plan_code = '{plan_code}' AND key = '{key}'"
            )
        else:
            op.execute(
                "UPDATE plan_entitlements "
                f"SET limit_value = {value}, is_unlimited = false "
                f"WHERE plan_code = '{plan_code}' AND key = '{key}'"
            )


def upgrade() -> None:
    """Upgrade schema."""
    _apply(NEW)


def downgrade() -> None:
    """Downgrade schema."""
    _apply(OLD)
