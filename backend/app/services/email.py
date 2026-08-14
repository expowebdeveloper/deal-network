"""SMTP delivery.

Uses SMTP_USER / SMTP_PASS from .env. For Gmail, SMTP_PASS must be an App
Password (a normal account password is refused when 2FA is on).

Sending never raises into a request: failures are logged and reported through
the return value, so a bad mail server cannot break sign-in.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "email"

_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html"]),
    enable_async=False,
)


def render(template_name: str, **context) -> str:
    return _env.get_template(template_name).render(
        frontend_url=settings.frontend_url,
        product_name=settings.smtp_from_name,
        **context,
    )


async def send_email(
    to: str | list[str],
    subject: str,
    html: str,
    text: str | None = None,
) -> bool:
    """Deliver one message. Returns False instead of raising when it cannot."""
    recipients = [to] if isinstance(to, str) else list(to)
    if not recipients:
        return False

    if not settings.email_configured:
        logger.warning(
            "Email skipped (SMTP not configured): to=%s subject=%r", recipients, subject
        )
        return False

    message = EmailMessage()
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_user}>"
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(text or _strip_html(html))
    message.add_alternative(html, subtype="html")

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_pass,
            start_tls=settings.smtp_starttls,
            timeout=20,
        )
    except (aiosmtplib.SMTPException, OSError) as exc:
        logger.error("Email failed: to=%s subject=%r error=%s", recipients, subject, exc)
        return False

    logger.info("Email sent: to=%s subject=%r", recipients, subject)
    return True


def _strip_html(html: str) -> str:
    """Crude plain-text fallback for clients that will not render HTML."""
    import re

    text = re.sub(r"<(br|/p|/div|/h[1-6])\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# --------------------------------------------------------------------------
# The messages the product actually sends
# --------------------------------------------------------------------------

async def send_welcome(to: str, name: str) -> bool:
    return await send_email(
        to,
        "Welcome to Deal Network",
        render("welcome.html", name=name),
    )


async def send_connection_request(to: str, to_name: str, from_name: str,
                                  from_company: str | None, note: str | None) -> bool:
    return await send_email(
        to,
        f"{from_name} wants to connect on Deal Network",
        render(
            "connection_request.html",
            to_name=to_name,
            from_name=from_name,
            from_company=from_company,
            note=note,
        ),
    )


async def send_connection_accepted(to: str, to_name: str, by_name: str) -> bool:
    return await send_email(
        to,
        f"{by_name} accepted your connection request",
        render("connection_accepted.html", to_name=to_name, by_name=by_name),
    )


async def send_introduction_request(to: str, to_name: str, from_name: str,
                                    from_company: str | None, via: str | None,
                                    message: str | None) -> bool:
    return await send_email(
        to,
        f"{from_name} asked for an introduction",
        render(
            "introduction_request.html",
            to_name=to_name,
            from_name=from_name,
            from_company=from_company,
            via=via,
            message=message,
        ),
    )


async def send_subscription_confirmation(to: str, name: str, plan: str, price: str) -> bool:
    return await send_email(
        to,
        f"You are on {plan}",
        render("subscription.html", name=name, plan=plan, price=price),
    )
