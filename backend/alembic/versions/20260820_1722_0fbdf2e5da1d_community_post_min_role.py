"""community post_min_role

Revision ID: 0fbdf2e5da1d
Revises: cc3c0bb1e7c9
Create Date: 2026-08-20 17:22:47.311068

Two adjustments to what autogenerate wrote, both of them things it cannot see:

  * `community_role` already exists — it is the membership role type. Plain
    `sa.Enum` would emit CREATE TYPE and fail, so the column is declared with
    `create_type=False`.
  * a NOT NULL column cannot be added to a table that already has rows without
    a default. One is supplied for the backfill and then dropped again, because
    the model declares only a Python-side `default=` — leaving the server
    default behind is exactly the drift revision 99d2eb24405d had to undo.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = '0fbdf2e5da1d'
down_revision: Union[str, Sequence[str], None] = 'cc3c0bb1e7c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

community_role = postgresql.ENUM(
    'owner', 'admin', 'moderator', 'member',
    name='community_role', create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'communities',
        sa.Column('post_min_role', community_role, nullable=False,
                  server_default='member'),
    )
    # Existing communities keep the behaviour they had: everyone may post.
    op.alter_column('communities', 'post_min_role', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('communities', 'post_min_role')
