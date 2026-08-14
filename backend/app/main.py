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
from app.core.config import settings
from app.core.database import create_all, engine
from app.core.limits import BodySizeLimitMiddleware
from app.services.oauth import available_providers

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("dealnetwork")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_all()

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
    max_bytes=max(settings.max_image_bytes, settings.max_document_bytes) + 1024 * 1024,
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
    ],
)

# Auth sits at /auth so the callback matches GOOGLE_REDIRECT_URI exactly.
app.include_router(auth.router)
app.include_router(api_router, prefix=settings.api_prefix)

# Uploaded files. Only allow-listed types are ever written here (see
# services/storage.py) and names are random, so there is nothing user-controlled
# in the path. `nosniff` stops a browser second-guessing the content type.
settings.upload_path.mkdir(parents=True, exist_ok=True)


class _NoSniffStatic(StaticFiles):
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response


app.mount("/media", _NoSniffStatic(directory=settings.upload_path), name="media")


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "oauth_providers": available_providers(),
        "email_configured": settings.email_configured,
    }


