"""The /api/v1 surface described by backend_flow.md.

Mounted alongside the pre-v1 `/api` routes rather than replacing them: the SPA
still calls `/api/communities`, and both prefixes read and write the same
tables. Section 35 asks for a versioned prefix precisely so the two can run
together while the frontend moves across.

Gating, outermost first:

    /api/v1/billing/plans          open — it is the public pricing page
    /api/v1/billing/signup-intent  open — chosen *before* an account exists
    /api/v1/billing/webhook        open to Stripe only; the signature is the auth
    /api/v1/billing/*              signed in, terms agreed
    /api/v1/entitlements/*         signed in, terms agreed
    /api/v1/communities/*          signed in, terms agreed, plan chosen

Billing deliberately stops at the terms gate. Requiring a chosen plan to reach
the endpoint that chooses a plan would be a deadlock.
"""

from fastapi import APIRouter, Depends

from app.api.deps import require_plan_selected, require_terms_accepted
from app.api.routes.v1 import billing, communities, entitlements, invites, members

terms_gate = [Depends(require_terms_accepted)]
full_gate = [Depends(require_terms_accepted), Depends(require_plan_selected)]

v1_router = APIRouter()

# Open, in registration order: the static /plans paths are declared before
# anything that could shadow them.
v1_router.include_router(billing.public_router)
v1_router.include_router(billing.webhook_router)

# Your own subscription, and what it entitles you to. Both stop at the terms
# gate rather than the plan gate: "what would this plan give me" is a question
# asked *while* choosing a plan, so requiring a chosen plan would lock the
# answer behind the decision it informs.
v1_router.include_router(billing.router, dependencies=terms_gate)
v1_router.include_router(entitlements.router, dependencies=terms_gate)

# The product proper. `members` is included after `communities` because its
# paths are all deeper than /communities/{id}, so no route is shadowed.
v1_router.include_router(communities.router, dependencies=full_gate)
v1_router.include_router(members.router, dependencies=full_gate)
v1_router.include_router(invites.router, dependencies=full_gate)

# The invitee's own endpoints. Off the /communities prefix on purpose: someone
# answering an invitation is not a member yet, so they cannot pass the
# membership checks the paths above apply — and an invitation to a private
# community has to be answerable without being able to read it first.
v1_router.include_router(invites.me_router, dependencies=full_gate)
