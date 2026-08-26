"""The domain error model from backend_flow.md section 23.

Every v1 endpoint reports refusals in one shape, so the SPA can switch on a
stable code instead of parsing prose:

    {"error": {"code": "COMMUNITY_LIMIT_REACHED",
               "message": "…",
               "details": {"limit": 10, "current": 10, "upgrade_plan": "professional"}}}

The pre-v1 routes still answer with FastAPI's `{"detail": …}`. Both shapes are
served by `install_error_handlers`, which keys off the raised exception type
rather than the URL, so a route gets the shape its own code chose.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# --- Codes ----------------------------------------------------------------
# Section 23's list, plus the few the endpoints below actually need. Kept as
# plain constants so a typo is an AttributeError at import rather than a string
# that silently reaches a client.

class Code:
    # Plan and entitlement
    PLAN_REQUIRED = "PLAN_REQUIRED"
    ENTITLEMENT_REQUIRED = "ENTITLEMENT_REQUIRED"
    SUBSCRIPTION_NOT_ACTIVE = "SUBSCRIPTION_NOT_ACTIVE"
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"

    # Community
    COMMUNITY_LIMIT_REACHED = "COMMUNITY_LIMIT_REACHED"
    PRIVATE_COMMUNITY_NOT_ALLOWED = "PRIVATE_COMMUNITY_NOT_ALLOWED"
    JOIN_POLICY_NOT_ALLOWED = "JOIN_POLICY_NOT_ALLOWED"
    COMMUNITY_NOT_FOUND = "COMMUNITY_NOT_FOUND"
    COMMUNITY_ACCESS_DENIED = "COMMUNITY_ACCESS_DENIED"
    COMMUNITY_ARCHIVED = "COMMUNITY_ARCHIVED"
    COMMUNITY_NOT_PUBLISHED = "COMMUNITY_NOT_PUBLISHED"
    COMMUNITY_MEMBER_LIMIT_REACHED = "COMMUNITY_MEMBER_LIMIT_REACHED"
    CHANNEL_LIMIT_REACHED = "CHANNEL_LIMIT_REACHED"

    # One code per ceiling, so a client can tell "you are out of contacts" from
    # "you are out of communities" without reading the prose. Every one of these
    # is raised only by services/entitlements.py, through the action registry.
    CONTACT_LIMIT_REACHED = "CONTACT_LIMIT_REACHED"
    TEAM_SEAT_LIMIT_REACHED = "TEAM_SEAT_LIMIT_REACHED"
    DATAROOM_INVITE_LIMIT_REACHED = "DATAROOM_INVITE_LIMIT_REACHED"
    UNDERWRITING_LIMIT_REACHED = "UNDERWRITING_LIMIT_REACHED"
    AI_SPEND_CAP_REACHED = "AI_SPEND_CAP_REACHED"

    # Membership
    MEMBERSHIP_REQUIRED = "MEMBERSHIP_REQUIRED"
    MEMBER_ALREADY_EXISTS = "MEMBER_ALREADY_EXISTS"
    MEMBER_NOT_FOUND = "MEMBER_NOT_FOUND"
    JOIN_REQUEST_ALREADY_EXISTS = "JOIN_REQUEST_ALREADY_EXISTS"
    JOIN_REQUEST_NOT_FOUND = "JOIN_REQUEST_NOT_FOUND"
    MEMBER_REMOVE_NOT_ALLOWED = "MEMBER_REMOVE_NOT_ALLOWED"
    MEMBER_BAN_NOT_ALLOWED = "MEMBER_BAN_NOT_ALLOWED"
    MEMBER_BANNED = "MEMBER_BANNED"
    ROLE_CHANGE_NOT_ALLOWED = "ROLE_CHANGE_NOT_ALLOWED"
    OWNER_REQUIRED = "OWNER_REQUIRED"
    PERMISSION_DENIED = "PERMISSION_DENIED"

    # Invitations
    INVITE_NOT_FOUND = "INVITE_NOT_FOUND"
    INVITE_ALREADY_EXISTS = "INVITE_ALREADY_EXISTS"
    INVITE_NOT_PENDING = "INVITE_NOT_PENDING"
    INVITE_EXPIRED = "INVITE_EXPIRED"
    INVITE_NOT_YOURS = "INVITE_NOT_YOURS"

    # Content and files (reserved — the modules that raise these come later)
    POST_AUDIENCE_NOT_ALLOWED = "POST_AUDIENCE_NOT_ALLOWED"
    MESSAGE_ACCESS_DENIED = "MESSAGE_ACCESS_DENIED"
    FILE_SIZE_LIMIT_EXCEEDED = "FILE_SIZE_LIMIT_EXCEEDED"
    STORAGE_QUOTA_EXCEEDED = "STORAGE_QUOTA_EXCEEDED"
    FILE_ACCESS_DENIED = "FILE_ACCESS_DENIED"
    CHANNEL_ACCESS_DENIED = "CHANNEL_ACCESS_DENIED"

    # Billing / Stripe
    BILLING_NOT_CONFIGURED = "BILLING_NOT_CONFIGURED"
    BILLING_ERROR = "BILLING_ERROR"
    SIGNUP_INTENT_INVALID = "SIGNUP_INTENT_INVALID"
    PLAN_UNKNOWN = "PLAN_UNKNOWN"
    WEBHOOK_SIGNATURE_INVALID = "WEBHOOK_SIGNATURE_INVALID"

    # Generic
    VALIDATION_FAILED = "VALIDATION_FAILED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class DomainError(Exception):
    """A refusal the client is meant to read and act on.

    Carries its own HTTP status so the rule that decided the refusal also
    decides how it is reported — routers do not re-map codes to statuses.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.headers = headers or {}

    def body(self) -> dict:
        error: dict = {"code": self.code, "message": self.message}
        if self.details:
            error["details"] = self.details
        return {"error": error}


# --- The shorthands the services actually raise ---------------------------

def not_found(code: str, message: str, **details) -> DomainError:
    return DomainError(code, message, status_code=status.HTTP_404_NOT_FOUND, details=details)


def forbidden(code: str, message: str, **details) -> DomainError:
    return DomainError(code, message, status_code=status.HTTP_403_FORBIDDEN, details=details)


def conflict(code: str, message: str, **details) -> DomainError:
    return DomainError(code, message, status_code=status.HTTP_409_CONFLICT, details=details)


def unprocessable(code: str, message: str, **details) -> DomainError:
    return DomainError(
        code, message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, details=details
    )


def payment_required(code: str, message: str, **details) -> DomainError:
    return DomainError(
        code, message, status_code=status.HTTP_402_PAYMENT_REQUIRED, details=details
    )


def unavailable(code: str, message: str, **details) -> DomainError:
    return DomainError(
        code, message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE, details=details
    )


def install_error_handlers(app: FastAPI) -> None:
    """Register the DomainError -> JSON translation.

    Note these run *inside* Starlette's exception middleware, which sits under
    CORSMiddleware — the same reason main.py catches unhandled errors in
    middleware rather than here. Handlers are fine: they return a response
    rather than letting the exception escape, so CORS still stamps its headers.
    """

    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        # Client mistakes are ordinary traffic; 5xx is ours and worth a trace.
        if exc.status_code >= 500:
            logger.error("Domain error %s on %s: %s", exc.code, request.url.path, exc.message)
        else:
            logger.debug("Domain error %s on %s: %s", exc.code, request.url.path, exc.message)
        return JSONResponse(
            status_code=exc.status_code, content=exc.body(), headers=exc.headers or None
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Body/query validation, in the domain shape for /api/v1 only.

        The pre-v1 routes and their tests read FastAPI's default 422 body, so
        only the versioned prefix gets the new shape.
        """
        if not request.url.path.startswith("/api/v1"):
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={"detail": _jsonable_errors(exc)},
            )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=DomainError(
                Code.VALIDATION_FAILED,
                "The request body did not validate.",
                details={"fields": _jsonable_errors(exc)},
            ).body(),
        )


def _jsonable_errors(exc: RequestValidationError) -> list[dict]:
    """Pydantic puts the offending value (and sometimes an exception) in `ctx`,
    which json.dumps cannot always serialise. Keep only what is safe to echo."""
    return [
        {
            "loc": [str(part) for part in error.get("loc", ())],
            "msg": error.get("msg", ""),
            "type": error.get("type", ""),
        }
        for error in exc.errors()
    ]
