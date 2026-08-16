"""
services/notification_service.py

Email notifications via SMTP (for email verification and password reset).
Falls back gracefully if SMTP is not configured — logs the link instead.
"""

from __future__ import annotations

import html
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)


async def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> bool:
    """
    Send an email via SMTP.

    Returns True on success, False if SMTP is unconfigured or fails.
    """
    from core.config import get_settings
    cfg = get_settings()

    if not cfg.has_smtp:
        logger.warning(
            "SMTP not configured — skipping email to %s (subject: %s)", to_email, subject
        )
        # Print the content so developers can still use the link in dev
        logger.info("EMAIL CONTENT:\n%s", text_body or html_body)
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = cfg.SMTP_FROM
        msg["To"] = to_email

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        # HIGH-4: Use aiosmtplib (async) instead of smtplib (sync/blocking).
        # smtplib.SMTP blocks the entire asyncio event loop during connection + TLS + send.
        try:
            import aiosmtplib  # type: ignore
            await aiosmtplib.send(
                msg,
                hostname=cfg.SMTP_HOST,
                port=cfg.SMTP_PORT,
                username=cfg.SMTP_USER,
                password=cfg.SMTP_PASS,
                start_tls=True,
            )
        except ImportError:
            # Graceful fallback if aiosmtplib not installed yet
            import asyncio
            import smtplib as _smtplib
            def _send_sync() -> None:
                with _smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT) as server:
                    server.ehlo()
                    server.starttls()
                    server.login(cfg.SMTP_USER, cfg.SMTP_PASS)
                    server.sendmail(cfg.SMTP_FROM, to_email, msg.as_string())
            await asyncio.to_thread(_send_sync)

        logger.info("Email sent to %s (subject: %s)", to_email, subject)
        return True

    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to_email, exc)
        return False


async def send_verification_email(email: str, token: str) -> bool:
    """Send an email address verification email."""
    from core.config import get_settings
    cfg = get_settings()
    link = f"{cfg.FRONTEND_URL}/verify-email?token={token}"

    subject = "Verify your SS SPARK email address"
    html = f"""
    <div style="font-family: 'Inter', sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
      <div style="text-align: center; margin-bottom: 32px;">
        <h1 style="color: #7c6ff7; font-size: 28px; margin: 0;">SS SPARK</h1>
        <p style="color: #888; margin-top: 4px;">AI Question Paper Analyzer</p>
      </div>
      <div style="background: #1a1a2e; border: 1px solid rgba(255,255,255,0.1);
                  border-radius: 16px; padding: 32px;">
        <h2 style="color: #fff; margin-top: 0;">Verify your email address</h2>
        <p style="color: #ccc; line-height: 1.6;">
          Click the button below to verify your email address and activate your account.
          This link expires in 24 hours.
        </p>
        <div style="text-align: center; margin: 32px 0;">
          <a href="{link}"
             style="background: linear-gradient(135deg, #7c6ff7, #a855f7);
                    color: white; padding: 14px 32px; border-radius: 10px;
                    text-decoration: none; font-weight: 600; font-size: 16px;">
            Verify Email Address
          </a>
        </div>
        <p style="color: #666; font-size: 13px;">
          Or copy this link: <a href="{link}" style="color: #7c6ff7;">{link}</a>
        </p>
      </div>
    </div>
    """
    text = f"Verify your SS SPARK email:\n\n{link}\n\nThis link expires in 24 hours."
    return await send_email(email, subject, html, text)


async def send_password_reset_email(email: str, token: str) -> bool:
    """Send a password reset email."""
    from core.config import get_settings
    cfg = get_settings()
    link = f"{cfg.FRONTEND_URL}/reset-password?token={token}"

    subject = "Reset your SS SPARK password"
    html = f"""
    <div style="font-family: 'Inter', sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
      <div style="text-align: center; margin-bottom: 32px;">
        <h1 style="color: #7c6ff7; font-size: 28px; margin: 0;">SS SPARK</h1>
        <p style="color: #888; margin-top: 4px;">AI Question Paper Analyzer</p>
      </div>
      <div style="background: #1a1a2e; border: 1px solid rgba(255,255,255,0.1);
                  border-radius: 16px; padding: 32px;">
        <h2 style="color: #fff; margin-top: 0;">Reset your password</h2>
        <p style="color: #ccc; line-height: 1.6;">
          You requested a password reset. Click the button below to choose a new password.
          This link expires in 1 hour. If you didn't request this, ignore this email.
        </p>
        <div style="text-align: center; margin: 32px 0;">
          <a href="{link}"
             style="background: linear-gradient(135deg, #7c6ff7, #a855f7);
                    color: white; padding: 14px 32px; border-radius: 10px;
                    text-decoration: none; font-weight: 600; font-size: 16px;">
            Reset Password
          </a>
        </div>
        <p style="color: #666; font-size: 13px;">
          Or copy this link: <a href="{link}" style="color: #7c6ff7;">{link}</a>
        </p>
      </div>
    </div>
    """
    text = f"Reset your SS SPARK password:\n\n{link}\n\nThis link expires in 1 hour."
    return await send_email(email, subject, html, text)


async def send_admin_notification_email(
    to_email: str,
    title: str,
    body: str,
) -> bool:
    """Send a platform announcement or notification from the admin."""
    subject = f"[SS SPARK] {title}"
    import html as _html
    safe_title = _html.escape(title)
    safe_body = _html.escape(body).replace("\n", "<br>")
    html_content = f"""
    <div style="font-family: 'Inter', sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
      <div style="text-align: center; margin-bottom: 32px;">
        <h1 style="color: #7c6ff7; font-size: 28px; margin: 0;">SS SPARK</h1>
      </div>
      <div style="background: #1a1a2e; border: 1px solid rgba(255,255,255,0.1);
                  border-radius: 16px; padding: 32px;">
        <h2 style="color: #fff; margin-top: 0;">{safe_title}</h2>
        <p style="color: #ccc; line-height: 1.6;">{safe_body}</p>
      </div>
    </div>
    """
    return await send_email(to_email, subject, html_content, body)
