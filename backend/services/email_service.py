"""
services/email_service.py

Production-ready, provider-agnostic email delivery service.

Supported providers (selected via EMAIL_PROVIDER env var):
  - resend      → Resend.com HTTP API  (recommended, free 3 000 emails/month)
  - smtp        → Any SMTP server (Gmail, Outlook, SendGrid SMTP relay, etc.)
  - log         → Development-only: log email content instead of sending

Provider selection:
  EMAIL_PROVIDER=resend    → RESEND_API_KEY must be set
  EMAIL_PROVIDER=smtp      → SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS must be set
  EMAIL_PROVIDER=log       → Logs body to console, always "succeeds" (dev only)
  <unset>                  → Auto-detect: resend → smtp → log

Configuration env vars:
  EMAIL_PROVIDER=resend | smtp | log
  EMAIL_FROM=noreply@yourdomain.com          (sender address shown to user)
  RESEND_API_KEY=re_xxxxxxxxxxxx             (Resend.com API key)
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=your@gmail.com
  SMTP_PASS=your-app-password-16-chars

IMPORTANT — Never log raw tokens, passwords, or API keys.
"""

from __future__ import annotations

import asyncio
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger("ss_spark.email")


def _get_provider() -> str:
    """Determine which email provider to use."""
    explicit = os.getenv("EMAIL_PROVIDER", "").strip().lower()
    if explicit in ("resend", "smtp", "log"):
        return explicit

    # Auto-detect based on available credentials
    if os.getenv("RESEND_API_KEY", "").strip():
        return "resend"
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_user = os.getenv("SMTP_USER", "").strip()
    if smtp_host and smtp_user:
        return "smtp"

    return "log"


def _get_from_address() -> str:
    from core.config import get_settings
    cfg = get_settings()
    # EMAIL_FROM takes priority over SMTP_FROM
    return (
        os.getenv("EMAIL_FROM", "").strip()
        or os.getenv("SMTP_FROM", "").strip()
        or cfg.SMTP_FROM
        or "noreply@ssspark.ai"
    )


async def _send_via_resend(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str],
    from_address: str,
) -> bool:
    """Send via Resend.com HTTP API."""
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    if not api_key:
        logger.error("[email] EMAIL_PROVIDER=resend but RESEND_API_KEY is not set.")
        return False

    try:
        import httpx
    except ImportError:
        logger.error("[email] httpx is required for Resend provider. Install it: pip install httpx")
        return False

    payload: dict = {
        "from": from_address,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }
    if text_body:
        payload["text"] = text_body

    logger.info("[email] Resend → sending to=%s subject=%r", to_email, subject)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if resp.status_code in (200, 201):
            data = resp.json()
            msg_id = data.get("id", "unknown")
            logger.info("[email] Resend → sent OK. id=%s", msg_id)
            return True
        else:
            # Log response body (no secrets) for debugging
            logger.error(
                "[email] Resend → HTTP %s error. body=%s",
                resp.status_code,
                resp.text[:500],
            )
            return False
    except Exception as exc:
        logger.error("[email] Resend → request failed: %s", exc)
        return False


async def _send_via_smtp(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str],
    from_address: str,
) -> bool:
    """Send via SMTP with STARTTLS (async using aiosmtplib or thread-pool fallback)."""
    from core.config import get_settings
    cfg = get_settings()

    smtp_host = os.getenv("SMTP_HOST", "").strip() or cfg.SMTP_HOST
    smtp_port_str = os.getenv("SMTP_PORT", "").strip() or str(cfg.SMTP_PORT)
    smtp_user = os.getenv("SMTP_USER", "").strip() or cfg.SMTP_USER
    smtp_pass = os.getenv("SMTP_PASS", "").strip() or cfg.SMTP_PASS

    if not smtp_host or not smtp_user:
        logger.error(
            "[email] SMTP provider requires SMTP_HOST and SMTP_USER. "
            "Current: host=%r user=%r",
            smtp_host, smtp_user,
        )
        return False

    smtp_port = int(smtp_port_str) if smtp_port_str.isdigit() else 587

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_address
    msg["To"] = to_email
    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    logger.info(
        "[email] SMTP → host=%s port=%d user=%s to=%s subject=%r",
        smtp_host, smtp_port, smtp_user, to_email, subject,
    )

    # Try aiosmtplib first (non-blocking), fall back to thread-pool smtplib
    try:
        import aiosmtplib  # type: ignore

        # For port 465 (SSL), use_tls=True. For 587 (STARTTLS), start_tls=True.
        if smtp_port == 465:
            await aiosmtplib.send(
                msg,
                hostname=smtp_host,
                port=smtp_port,
                username=smtp_user,
                password=smtp_pass,
                use_tls=True,
            )
        else:
            await aiosmtplib.send(
                msg,
                hostname=smtp_host,
                port=smtp_port,
                username=smtp_user,
                password=smtp_pass,
                start_tls=True,
            )
        logger.info("[email] SMTP → sent OK to %s", to_email)
        return True

    except ImportError:
        logger.debug("[email] aiosmtplib not found — using thread-pool smtplib fallback")

    except Exception as exc:
        logger.error("[email] SMTP (aiosmtplib) → failed: %s", exc)
        return False

    # Thread-pool smtplib fallback
    def _send_sync() -> None:
        import smtplib
        if smtp_port == 465:
            import ssl as _ssl
            ctx = _ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx) as server:
                server.login(smtp_user, smtp_pass)
                server.sendmail(from_address, to_email, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_user, smtp_pass)
                server.sendmail(from_address, to_email, msg.as_string())

    try:
        await asyncio.to_thread(_send_sync)
        logger.info("[email] SMTP (smtplib fallback) → sent OK to %s", to_email)
        return True
    except Exception as exc:
        logger.error("[email] SMTP (smtplib fallback) → failed: %s", exc)
        return False


async def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> bool:
    """
    Send an email through the configured provider.

    Returns True on success, False on failure.
    Never raises — always returns a bool.

    Logs are safe: no tokens, passwords, or API keys are logged.
    """
    provider = _get_provider()
    from_address = _get_from_address()

    logger.info(
        "[email] Provider=%s from=%s to=%s",
        provider, from_address, to_email,
    )

    if provider == "resend":
        return await _send_via_resend(to_email, subject, html_body, text_body, from_address)

    if provider == "smtp":
        return await _send_via_smtp(to_email, subject, html_body, text_body, from_address)

    # "log" mode — development fallback
    logger.warning(
        "[email] No email provider configured (EMAIL_PROVIDER=log). "
        "Email NOT sent. To=%s Subject=%r\n"
        "Set RESEND_API_KEY or SMTP_HOST+SMTP_USER+SMTP_PASS to send real emails.\n"
        "Reset link has been logged to INFO below.",
        to_email, subject,
    )
    # Log the text body so devs can use the link during development
    logger.info("[email] DEV_CONTENT:\n%s", text_body or "[html only]")
    # Return True in log/dev mode so the frontend shows success to devs
    return True
