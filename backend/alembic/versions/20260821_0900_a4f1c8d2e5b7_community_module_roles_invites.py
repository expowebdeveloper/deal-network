"""community module: viewer role, invitations, four personas, freemium cannot create

Revision ID: a4f1c8d2e5b7
Revises: c248ea836ef0
Create Date: 2026-08-21 09:00:00.000000

Four changes, in the order they have to happen (the second carries three new
`notification_kind` values with it):

1. **`viewer` on `community_role`.** A read-only standing below `member`. Added
   in an autocommit block, because `ALTER TYPE … ADD VALUE` cannot be followed
   by a use of that value in the same transaction.

2. **`community_invites`.** The invitation table, with its own `invite_status`
   type. Two *partial* unique indexes rather than plain ones: only a `pending`
   row occupies the slot, so declining and being re-invited works and the
   history rows do not collide.

3. **`member_role` loses `service_provider`.** Personas are Developer,
   Investor, Broker and Lender. Postgres cannot drop an enum value, so the type
   is rebuilt and all three columns that use it are recast.

   **This is the one lossy step in the revision.** Any account whose persona was
   `service_provider` is set to NULL, which is the same state a member has
   before they finish onboarding — they are asked to pick again. The count is
   raised as a notice so it appears in the migration output.

4. **Freemium loses community creation.** `community.create` off and
   `community.max_owned` at 0 for `early_access`. The matrices in
   `services/entitlements.py` are the defaults; these rows are what an already
   seeded database actually reads, so both have to move or a deployed
   environment keeps the old behaviour.

The downgrade restores 1, 3 and 4 as far as Postgres allows. `viewer` cannot be
removed from the enum without rebuilding it, and any membership sitting at
`viewer` is moved to `member` first so nothing dangles.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a4f1c8d2e5b7'
down_revision: Union[str, Sequence[str], None] = 'c248ea836ef0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERSONAS_NEW = ('developer', 'investor', 'broker', 'lender')
PERSONAS_OLD = ('developer', 'investor', 'broker', 'lender', 'service_provider')

#: Every table.column carrying `member_role`.
PERSONA_COLUMNS = (
    ('users', 'role'),
    ('contacts', 'role'),
    ('member_onboarding', 'role'),
)


def _rebuild_member_role(values: tuple[str, ...]) -> None:
    """Recreate `member_role` with `values` and recast every column onto it.

    Rename-create-cast-drop is the only way to change an enum's membership in
    Postgres. Each column is cast through text, which is why the old and new
    types only have to agree on the values actually stored.
    """
    op.execute("ALTER TYPE member_role RENAME TO member_role_old")
    sa.Enum(*values, name='member_role').create(op.get_bind())
    for table, column in PERSONA_COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} "
            f"TYPE member_role USING {column}::text::member_role"
        )
    op.execute("DROP TYPE member_role_old")


def upgrade() -> None:
    """Upgrade schema."""
    # --- 1. viewer -------------------------------------------------------
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE community_role ADD VALUE IF NOT EXISTS 'viewer'")

    # --- 2. invitations --------------------------------------------------
    # The three notification kinds the invitation flow raises. Same autocommit
    # rule as `viewer` above, and the same reason autogenerate would not have
    # caught them: a new *value* on an existing enum is invisible to it.
    with op.get_context().autocommit_block():
        for kind in (
            'community_invite', 'community_invite_accepted', 'community_invite_declined',
        ):
            op.execute(f"ALTER TYPE notification_kind ADD VALUE IF NOT EXISTS '{kind}'")

    invite_status = postgresql.ENUM(
        'pending', 'accepted', 'declined', 'revoked', 'expired',
        name='invite_status',
    )
    invite_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'community_invites',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('community_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invited_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('email', sa.String(length=320), nullable=True),
        sa.Column('invited_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            'role',
            postgresql.ENUM(
                'owner', 'admin', 'moderator', 'member', 'viewer',
                name='community_role', create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            'status',
            postgresql.ENUM(
                'pending', 'accepted', 'declined', 'revoked', 'expired',
                name='invite_status', create_type=False,
            ),
            nullable=False,
        ),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_community_invites_community_id'), 'community_invites', ['community_id']
    )
    op.create_index(
        op.f('ix_community_invites_invited_user_id'), 'community_invites',
        ['invited_user_id'],
    )
    op.create_index(op.f('ix_community_invites_email'), 'community_invites', ['email'])
    op.create_index(op.f('ix_community_invites_status'), 'community_invites', ['status'])
    op.create_index(
        op.f('ix_community_invites_token'), 'community_invites', ['token'], unique=True
    )
    # Partial: one *live* invitation per person per community.
    op.create_index(
        'uq_invite_pending_user', 'community_invites',
        ['community_id', 'invited_user_id'], unique=True,
        postgresql_where=sa.text("status = 'pending' AND invited_user_id IS NOT NULL"),
    )
    op.create_index(
        'uq_invite_pending_email', 'community_invites',
        ['community_id', 'email'], unique=True,
        postgresql_where=sa.text("status = 'pending' AND email IS NOT NULL"),
    )

    # --- 3. four personas ------------------------------------------------
    conn = op.get_bind()
    affected = conn.execute(
        sa.text("SELECT count(*) FROM users WHERE role = 'service_provider'")
    ).scalar() or 0
    if affected:
        # Raised as a notice so it is visible in the migration output rather
        # than only discoverable afterwards.
        op.execute(
            sa.text(
                "DO $$ BEGIN RAISE NOTICE "
                "'community module: clearing service_provider persona from % account(s)', "
                f"{int(affected)}; END $$"
            )
        )
    for table, column in PERSONA_COLUMNS:
        op.execute(
            f"UPDATE {table} SET {column} = NULL WHERE {column} = 'service_provider'"
        )
    _rebuild_member_role(PERSONAS_NEW)

    # --- 4. freemium cannot create ---------------------------------------
    op.execute(
        "UPDATE plan_entitlements SET enabled = false "
        "WHERE plan_code = 'early_access' AND key = 'community.create'"
    )
    op.execute(
        "UPDATE plan_entitlements SET limit_value = 0, is_unlimited = false "
        "WHERE plan_code = 'early_access' AND key = 'community.max_owned'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # --- 4. freemium regains creation ------------------------------------
    op.execute(
        "UPDATE plan_entitlements SET enabled = true "
        "WHERE plan_code = 'early_access' AND key = 'community.create'"
    )
    op.execute(
        "UPDATE plan_entitlements SET limit_value = 1, is_unlimited = false "
        "WHERE plan_code = 'early_access' AND key = 'community.max_owned'"
    )

    # --- 3. the fifth persona --------------------------------------------
    # The accounts cleared on the way up are not recoverable; this only makes
    # the value selectable again.
    _rebuild_member_role(PERSONAS_OLD)

    # --- 2. invitations ---------------------------------------------------
    op.drop_index('uq_invite_pending_email', table_name='community_invites')
    op.drop_index('uq_invite_pending_user', table_name='community_invites')
    op.drop_index(op.f('ix_community_invites_token'), table_name='community_invites')
    op.drop_index(op.f('ix_community_invites_status'), table_name='community_invites')
    op.drop_index(op.f('ix_community_invites_email'), table_name='community_invites')
    op.drop_index(
        op.f('ix_community_invites_invited_user_id'), table_name='community_invites'
    )
    op.drop_index(
        op.f('ix_community_invites_community_id'), table_name='community_invites'
    )
    op.drop_table('community_invites')
    sa.Enum(name='invite_status').drop(op.get_bind(), checkfirst=True)

    # --- 1. viewer --------------------------------------------------------
    # Nothing may be left sitting at a value the rebuilt type will not have.
    op.execute(
        "UPDATE community_members SET role = 'member', is_admin = false "
        "WHERE role = 'viewer'"
    )
    op.execute("UPDATE communities SET post_min_role = 'member' WHERE post_min_role = 'viewer'")
    op.execute("ALTER TYPE community_role RENAME TO community_role_old")
    sa.Enum('owner', 'admin', 'moderator', 'member', name='community_role').create(
        op.get_bind()
    )
    for table, column in (
        ('community_members', 'role'),
        ('communities', 'post_min_role'),
    ):
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT"
        )
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} "
            f"TYPE community_role USING {column}::text::community_role"
        )
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT 'member'"
        )
    op.execute("DROP TYPE community_role_old")
