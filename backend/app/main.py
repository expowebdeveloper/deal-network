"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.api.routes import auth
from app.api.v1_router import v1_router
from app.core.config import settings
from app.core.database import engine, schema_revision
from app.core.errors import install_error_handlers
from app.core.limits import BodySizeLimitMiddleware
from app.services import files as file_service
from app.services.oauth import available_providers

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("dealnetwork")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Alembic owns the schema — the app no longer creates tables on boot. Say
    # plainly whether this database has been migrated, so a forgotten
    # `alembic upgrade head` shows up here and not as a mystifying
    # "relation does not exist" on the first request that touches a new table.
    revision = await schema_revision()
    if revision is None:
        logger.error(
            "Database has no Alembic version stamp — the schema is missing or was "
            "built by hand. Run `alembic upgrade head` in backend/ before serving."
        )
    else:
        logger.info("Database schema at Alembic revision %s", revision)

    providers = available_providers()
    if providers:
        logger.info("OAuth providers enabled: %s", ", ".join(providers))
    else:
        logger.warning(
            "No OAuth provider is configured — set GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET in backend/.env to enable sign-in."
        )

    if not settings.email_configured:
        logger.warning("SMTP is not configured — emails will be logged and skipped.")

    # The plan ceilings are the product's promise; the upload limits in .env are
    # what this deployment can actually carry. When the second is smaller, a
    # paying member's uploads are capped below their tier — say so at startup
    # rather than letting it surface as a puzzling 422.
    capped, largest_plan, deployment = file_service.plan_exceeds_deployment()
    if capped:
        logger.warning(
            "Upload cap: plans allow up to %s per file but this deployment accepts "
            "%s (MAX_IMAGE_BYTES / MAX_VIDEO_BYTES / MAX_DOCUMENT_BYTES). Paid tiers are capped at the "
            "smaller figure. Raising it needs object storage — see backend_flow.md 19.",
            file_service.human(largest_plan), file_service.human(deployment),
        )

    if not settings.stripe_enabled:
        logger.warning(
            "Stripe is not configured — /api/v1/billing checkout, portal and webhook "
            "endpoints will answer 503. Set STRIPE_SECRET_KEY in backend/.env."
        )
    else:
        missing = [
            name for name, value in (
                ("STRIPE_WEBHOOK_SECRET", settings.stripe_webhook_secret),
                ("STRIPE_PRICE_MEMBER", settings.stripe_price_member),
                ("STRIPE_PRICE_PROFESSIONAL", settings.stripe_price_professional),
            ) if not value
        ]
        if missing:
            # Without the webhook secret no payment can ever be applied, so this
            # is a broken billing setup rather than a partial one.
            logger.warning("Stripe is configured but these are unset: %s", ", ".join(missing))
        logger.info(
            "Stripe enabled in %s mode", "LIVE" if settings.stripe_live_mode else "test"
        )

    yield
    await engine.dispose()


app = FastAPI(
    title="Deal Network API",
    description="Backend for the Deal Network property professional network.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

@app.middleware("http")
async def catch_unhandled_errors(request: Request, call_next):
    """Turn an unhandled exception into JSON.

    Registered as middleware rather than an exception_handler because Starlette
    serves exception handlers *outside* the CORS middleware — the browser would
    then report a CORS failure instead of showing the 500 body.

    Registration order matters: this must be added BEFORE CORSMiddleware so that
    CORS ends up on the outside and can stamp its headers onto this response.
    """
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Something went wrong"},
        )


# Reject oversized bodies before anything parses them. Added after the error
# handler and before CORS, so the final order is:
#   CORS -> body size limit -> error handler -> routing
app.add_middleware(
    BodySizeLimitMiddleware,
    # The widest per-type ceiling plus a megabyte of multipart overhead — a
    # video is the largest thing that legitimately arrives, so sizing this on
    # documents alone would reject one before any handler saw it.
    max_bytes=file_service.deployment_ceiling() + 1024 * 1024,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # A browser can only read response headers that are named here. These carry
    # why a call was refused — see deps.require_feature — so without them the
    # SPA would get the 403 but not what to upgrade to.
    expose_headers=[
        "X-Required-Plan", "X-Required-Feature", "X-Required-Phase", "X-Contact-Limit",
        "X-Community-Limit",
    ],
)

# Turn DomainError into backend_flow.md section 23's response shape.
install_error_handlers(app)

# Auth sits at /auth so the callback matches GOOGLE_REDIRECT_URI exactly.
app.include_router(auth.router)
app.include_router(api_router, prefix=settings.api_prefix)
# The versioned surface from backend_flow.md. Runs alongside the routes above,
# on the same tables — see app/api/v1_router.py.
app.include_router(v1_router, prefix=f"{settings.api_prefix}/v1")

# Uploaded files. Only allow-listed types are ever written here (see
# services/storage.py) and names are random, so there is nothing user-controlled
# in the path. `nosniff` stops a browser second-guessing the content type.
settings.upload_path.mkdir(parents=True, exist_ok=True)


class _NoSniffStatic(StaticFiles):
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Content-Disposition"] = "inline"
        return response


app.mount("/media", _NoSniffStatic(directory=settings.upload_path), name="media")


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "oauth_providers": available_providers(),
        "email_configured": settings.email_configured,
        # Whether card payments can be taken at all. Booleans only — never the
        # keys, and not which one is missing.
        "stripe_configured": settings.stripe_enabled,
        "stripe_webhook_ready": settings.stripe_webhook_ready,
    }


