"""add-on catalogue, prices, entitlement effects and purchases

Revision ID: e64b9d3a71c5
Revises: d51b8ac47f92
Create Date: 2026-08-24 10:00:00.000000

The add-on layer from community_role_and_subs.md sections 15 and 16 — the step
between a plan's base entitlements and the effective limit the entitlement
service compares usage against.

Four tables, in dependency order:

    addons                      the catalogue, keyed by a stable `code`
    addon_prices                what it costs, optionally per plan
    addon_entitlement_effects   which entitlement key it raises, and by how much
    addon_subscriptions         who holds it, and how many

`addon_code` foreign keys point at `addons.code` rather than `addons.id`, the
same way `plan_entitlements.plan_code` points at `plans.code`: the code is the
identifier the product, the logs and the seed data all use, and it is unique.

Nothing is seeded here — this is schema. `python seed_plans.py` writes the
proposed catalogue, whose prices section 25.3 of the spec still lists as
unconfirmed. Until it is run, `services/addons.load` returns an empty catalogue
and every blocked action offers an upgrade and no add-on, which is correct: an
add-on with no price cannot be bought.

The downgrade drops all four. Purchases are Stripe-backed, so the billing
records survive in Stripe; nothing here is the only copy of a payment.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'e64b9d3a71c5'
down_revision: Union[str, Sequence[str], None] = 'd51b8ac47f92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# `plan_tier` already exists (plans, subscriptions), so the reference below must
# not try to create it again.
plan_tier = postgresql.ENUM(
    'early_access', 'member', 'professional', name='plan_tier', create_type=False
)
# Two objects per new type: one that creates it, and one with
# `create_type=False` for the column definitions. Without the second,
# `create_table` emits its own CREATE TYPE and the migration fails on the
# duplicate.
ADDON_STATUS_VALUES = ('active', 'past_due', 'cancelled', 'expired')
ADDON_EFFECT_VALUES = ('increment', 'set_to', 'unlimited', 'enable')

addon_status_type = postgresql.ENUM(*ADDON_STATUS_VALUES, name='addon_status')
addon_effect_type = postgresql.ENUM(*ADDON_EFFECT_VALUES, name='addon_effect')

addon_status = postgresql.ENUM(
    *ADDON_STATUS_VALUES, name='addon_status', create_type=False
)
addon_effect = postgresql.ENUM(
    *ADDON_EFFECT_VALUES, name='addon_effect', create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    addon_status_type.create(bind, checkfirst=True)
    addon_effect_type.create(bind, checkfirst=True)

    op.create_table(
        'addons',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('code', sa.String(length=60), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('unit', sa.String(length=40), nullable=False, server_default=''),
        sa.Column('max_quantity', sa.Integer(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint('code', name='uq_addons_code'),
    )
    op.create_index('ix_addons_code', 'addons', ['code'])

    op.create_table(
        'addon_prices',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('addon_code', sa.String(length=60), nullable=False),
        # NULL means "on any plan"; a pinned row wins over it for that plan.
        sa.Column('plan_code', plan_tier, nullable=True),
        sa.Column('price_usd', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(length=8), nullable=False, server_default='usd'),
        sa.Column(
            'billing_interval', sa.String(length=16), nullable=False, server_default='month',
        ),
        sa.Column('stripe_price_id', sa.String(length=80), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['addon_code'], ['addons.code'],
            name='fk_addon_prices_addon', ondelete='CASCADE',
        ),
        sa.UniqueConstraint(
            'addon_code', 'plan_code', 'billing_interval', name='uq_addon_price',
        ),
    )
    op.create_index('ix_addon_prices_addon_code', 'addon_prices', ['addon_code'])

    op.create_table(
        'addon_entitlement_effects',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('addon_code', sa.String(length=60), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('key', sa.String(length=80), nullable=False),
        sa.Column(
            'effect', addon_effect, nullable=False, server_default='increment',
        ),
        sa.Column('amount', sa.Numeric(20, 0), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['addon_code'], ['addons.code'],
            name='fk_addon_effects_addon', ondelete='CASCADE',
        ),
        # One row per key per add-on: a bundle that raises two ceilings is two
        # rows, not a special case.
        sa.UniqueConstraint('addon_code', 'key', name='uq_addon_effect_key'),
    )
    op.create_index(
        'ix_addon_entitlement_effects_addon_code', 'addon_entitlement_effects', ['addon_code'],
    )

    op.create_table(
        'addon_subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('addon_code', sa.String(length=60), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', addon_status, nullable=False, server_default='active'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        # NULL means "until cancelled". A past date stops granting immediately,
        # with no sweeper job — services/addons compares against the clock.
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stripe_subscription_item_id', sa.String(length=80), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name='fk_addon_subscriptions_user', ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['addon_code'], ['addons.code'],
            name='fk_addon_subscriptions_addon', ondelete='CASCADE',
        ),
        # Quantity rather than a row per unit, so "three extra communities" is
        # one row — which is also how Stripe models a subscription item.
        sa.UniqueConstraint('user_id', 'addon_code', name='uq_addon_subscription_owner'),
        sa.UniqueConstraint(
            'stripe_subscription_item_id', name='uq_addon_subscription_stripe_item',
        ),
    )
    op.create_index('ix_addon_subscriptions_user_id', 'addon_subscriptions', ['user_id'])
    op.create_index(
        'ix_addon_subscriptions_addon_code', 'addon_subscriptions', ['addon_code'],
    )
    op.create_index(
        'ix_addon_subscriptions_stripe_item', 'addon_subscriptions',
        ['stripe_subscription_item_id'],
    )


def downgrade() -> None:
    op.drop_table('addon_subscriptions')
    op.drop_table('addon_entitlement_effects')
    op.drop_table('addon_prices')
    op.drop_index('ix_addons_code', table_name='addons')
    op.drop_table('addons')

    bind = op.get_bind()
    addon_effect_type.drop(bind, checkfirst=True)
    addon_status_type.drop(bind, checkfirst=True)
