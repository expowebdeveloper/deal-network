"""Seed the plan catalogue — `plans`, `plan_entitlements` and the add-ons.

    python seed_plans.py             # fill in whatever is missing
    python seed_plans.py --reset     # overwrite existing rows with the defaults

This is data, not schema, so it is not part of an Alembic revision. It used to
ride along with `migrate.py`; that script is legacy now, and this is where the
step lives.

Seeding is optional: `services/entitlements.py` falls back to built-in defaults
when these tables are empty. What it buys is configurability — once the rows
exist, a limit can be tuned in the database instead of in code. Without
`--reset` an already-tuned limit survives a re-run.
"""

from __future__ import annotations

import asyncio
import sys

from app.core.database import AsyncSessionLocal, schema_revision
from app.services.addons import seed_addons
from app.services.plan_catalogue import seed_plans


async def main() -> None:
    if await schema_revision() is None:
        sys.exit("Database is not migrated — run `alembic upgrade head` first.")

    reset = "--reset" in sys.argv
    async with AsyncSessionLocal() as db:
        result = await seed_plans(db, overwrite=reset)
        # The add-on catalogue is seeded in the same pass. Without it, a member
        # who hits a ceiling is offered an upgrade and no add-on — correct, but
        # only half the flow in section 16.
        addons = await seed_addons(db, overwrite=reset)

    print(
        f"{result['plans_created']} plans created, {result['plans_updated']} updated, "
        f"{result['entitlements_created']} entitlements created, "
        f"{result['entitlements_updated']} updated"
    )
    print(
        f"{addons['addons_created']} add-ons created, {addons['addons_updated']} updated, "
        f"{addons['addons_retired']} retired, {addons['effects_created']} effects created, "
        f"{addons['prices_created']} prices created"
    )


if __name__ == "__main__":
    asyncio.run(main())
