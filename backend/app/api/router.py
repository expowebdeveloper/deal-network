"""Collects the resource routers that live under the /api prefix.

Two gates stand between signing in and the product, in this order:

    /api/me, /api/terms          always reachable — you need them to get through
    /api/plans/catalogue         open to anyone, signed in or not
    /api/plans                   behind `require_terms_accepted`
    everything else              behind both gates

So a new member can sign in, read the terms, agree to them, pick a plan, and
nothing else until they have.
"""

from fastapi import APIRouter, Depends

from app.api.deps import require_plan_selected, require_terms_accepted
from app.api.routes import (
    communities, contacts, investors, media, onboarding, plans, posts, terms, users,
)

terms_gate = [Depends(require_terms_accepted)]
gated = [Depends(require_terms_accepted), Depends(require_plan_selected)]

api_router = APIRouter()

# Open: identity, the terms themselves, and the price list the public pricing
# page runs on. Registered before the gated plans router so /plans/catalogue
# resolves here rather than behind the terms gate.
api_router.include_router(users.router)
api_router.include_router(terms.router)
api_router.include_router(plans.public_router)

# The plan step, which only opens once the terms are agreed to.
api_router.include_router(plans.router, dependencies=terms_gate)

# Profile setup, which follows the plan step. Behind both gates: there is
# nothing to set up until a member has agreed to the terms and picked a tier.
api_router.include_router(onboarding.router, dependencies=gated)

# Gated: the actual product.
api_router.include_router(communities.router, dependencies=gated)
api_router.include_router(posts.router, dependencies=gated)
api_router.include_router(media.router, dependencies=gated)
api_router.include_router(contacts.router, dependencies=gated)
api_router.include_router(investors.router, dependencies=gated)
