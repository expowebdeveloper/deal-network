"""community draft stage, publish timestamp, and invite_min_role

Revision ID: d51b8ac47f92
Revises: c93a5f7e21d8
Create Date: 2026-08-21 15:00:00.000000

Three related changes, all in service of "a community is built before it is
launched, and its own members can grow it":

1. **`draft` on `community_status`.** Every community is now created as a draft:
   editable by the people who can manage it, invisible to everyone else, and not
   joinable. Publishing is the one-way move to `active`. Added in an autocommit
   block, because `ALTER TYPE … ADD VALUE` cannot be followed by a use of that
   value in the same transaction.

2. **`communities.published_at`.** When it first went live. Backfilled from
   `created_at` for every community that already exists, because they are all
   already published — leaving it null would make them look like drafts to
   anything that reads `is_published`.

3. **`communities.invite_min_role`.** The lowest role allowed to send an
   invitation, stored exactly like `post_min_role`. Defaults to `admin`, which
   is the behaviour before this revision, so nothing changes for an existing
   community until someone opts in by setting it to `member`.

The downgrade moves any surviving draft to `active` before rebuilding the enum,
so nothing is left pointing at a value the older type does not have.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'd51b8ac47f92'
down_revision: Union[str, Sequence[str], None] = 'c93a5f7e21d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE community_status ADD VALUE IF NOT EXISTS 'draft'")

    op.add_column(
        'communities',
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'communities',
        sa.Column(
            'invite_min_role',
            postgresql.ENUM(
                'owner', 'admin', 'moderator', 'member', 'viewer',
                name='community_role', create_type=False,
            ),
            nullable=False,
            server_default='admin',
        ),
    )

    # Everything that exists today is live, so it is published. Archived ones
    # included: archiving takes a community down, it does not return it to draft.
    op.execute(
        "UPDATE communities SET published_at = created_at WHERE published_at IS NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('communities', 'invite_min_role')
    op.drop_column('communities', 'published_at')

    # Nothing may be left at a value the rebuilt type will not carry.
    op.execute("UPDATE communities SET status = 'active' WHERE status = 'draft'")
    op.execute("ALTER TYPE community_status RENAME TO community_status_old")
    sa.Enum('active', 'archived', 'deleted', name='community_status').create(op.get_bind())
    op.execute("ALTER TABLE communities ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE communities ALTER COLUMN status "
        "TYPE community_status USING status::text::community_status"
    )
    op.execute("ALTER TABLE communities ALTER COLUMN status SET DEFAULT 'active'")
    op.execute("DROP TYPE community_status_old")
