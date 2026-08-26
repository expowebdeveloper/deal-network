"""media kind video

Revision ID: c248ea836ef0
Revises: 0fbdf2e5da1d
Create Date: 2026-08-20 17:37:00.000000

Adds `video` to the `media_kind` enum so posts can carry video attachments.

Written by hand: autogenerate compares tables and columns, and never notices a
new *value* on an existing enum — the blind spot the README warns about. It also
runs in an autocommit block, because `ALTER TYPE … ADD VALUE` may not be
followed by a use of that value inside the same transaction.

The downgrade is deliberately a no-op. Postgres cannot drop a value from an enum
without rebuilding the type and rewriting every column that uses it, and nothing
depends on `video` being absent — an older build simply never writes it.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'c248ea836ef0'
down_revision: Union[str, Sequence[str], None] = '0fbdf2e5da1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE media_kind ADD VALUE IF NOT EXISTS 'video'")


def downgrade() -> None:
    """Downgrade schema."""
    # Intentionally empty — see the module docstring.
    pass
