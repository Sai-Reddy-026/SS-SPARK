"""
services/notification_service.py

Email notifications — delegates to services/email_service.py for delivery.

This module builds the email HTML/text content.
Actual sending is handled by email_service.send_email(), which supports
Resend.com, SMTP, or log-mode depending on environment variables.
"""

from __future__ import annotations

import logging
from typing import Optional

from services.email_service import send_email

logger = logging.getLogger(__name__)


def _get_frontend_url() -> str:
    from core.config import get_settings
    return get_settings().FRONTEND_URL.rstrip("/")


async def send_verification_email(email: str, token: str) -> bool:
    """Send an email address verification email."""
    frontend_url = _get_frontend_url()
    link = f"{frontend_url}/verify-email?token={token}"

    subject = "Verify your SS SPARK email address"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#0d0d1a;font-family:'Inter',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0d0d1a;padding:40px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
        <!-- Header -->
        <tr><td align="center" style="padding-bottom:32px;">
          <h1 style="color:#8b5cf6;font-size:28px;margin:0;letter-spacing:-0.5px;">SS SPARK</h1>
          <p style="color:#6b7280;margin:4px 0 0;">AI Question Paper Analyzer</p>
        </td></tr>
        <!-- Card -->
        <tr><td style="background:#1a1a2e;border:1px solid rgba(255,255,255,0.1);border-radius:16px;padding:40px;">
          <h2 style="color:#fff;margin:0 0 16px;font-size:22px;">Verify your email address</h2>
          <p style="color:#cbd5e1;line-height:1.7;margin:0 0 32px;">
            Click the button below to verify your email address and activate your account.
            This link expires in <strong style="color:#fff;">24 hours</strong>.
          </p>
          <div style="text-align:center;margin:32px 0;">
            <a href="{link}"
               style="background:linear-gradient(135deg,#7c3aed,#a855f7);color:#fff;
                      padding:14px 36px;border-radius:10px;text-decoration:none;
                      font-weight:600;font-size:16px;display:inline-block;">
              Verify Email Address
            </a>
          </div>
          <p style="color:#6b7280;font-size:13px;margin:24px 0 0;line-height:1.6;">
            Or paste this link in your browser:<br>
            <a href="{link}" style="color:#8b5cf6;word-break:break-all;">{link}</a>
          </p>
          <hr style="border:none;border-top:1px solid rgba(255,255,255,0.08);margin:24px 0;">
          <p style="color:#6b7280;font-size:12px;margin:0;">
            If you didn't create an SS SPARK account, you can safely ignore this email.
          </p>
        </td></tr>
        <!-- Footer -->
        <tr><td align="center" style="padding-top:24px;">
          <p style="color:#4b5563;font-size:12px;margin:0;">
            © 2025 SS SPARK · AI Question Paper Analyzer
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    text = (
        f"Verify your SS SPARK email\n\n"
        f"Click the link below to verify your email address:\n{link}\n\n"
        f"This link expires in 24 hours.\n\n"
        f"If you didn't create an account, ignore this email."
    )

    return await send_email(email, subject, html, text)


async def send_password_reset_email(email: str, token: str) -> bool:
    """
    Send a password reset email.

    `token` is the raw (unhashed) reset token to embed in the URL.
    """
    frontend_url = _get_frontend_url()
    link = f"{frontend_url}/reset-password?token={token}"

    logger.info("[notification] Building password reset email for %s — link domain: %s", email, frontend_url)

    subject = "Reset your SS SPARK password"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#0d0d1a;font-family:'Inter',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0d0d1a;padding:40px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
        <!-- Header -->
        <tr><td align="center" style="padding-bottom:32px;">
          <h1 style="color:#8b5cf6;font-size:28px;margin:0;letter-spacing:-0.5px;">SS SPARK</h1>
          <p style="color:#6b7280;margin:4px 0 0;">AI Question Paper Analyzer</p>
        </td></tr>
        <!-- Card -->
        <tr><td style="background:#1a1a2e;border:1px solid rgba(255,255,255,0.1);border-radius:16px;padding:40px;">
          <h2 style="color:#fff;margin:0 0 16px;font-size:22px;">Reset your password</h2>
          <p style="color:#cbd5e1;line-height:1.7;margin:0 0 8px;">Hello,</p>
          <p style="color:#cbd5e1;line-height:1.7;margin:0 0 32px;">
            We received a request to reset your SS SPARK password.
            Click the button below to choose a new password.
            This link expires in <strong style="color:#fff;">30 minutes</strong>.
          </p>
          <div style="text-align:center;margin:32px 0;">
            <a href="{link}"
               style="background:linear-gradient(135deg,#7c3aed,#a855f7);color:#fff;
                      padding:14px 36px;border-radius:10px;text-decoration:none;
                      font-weight:600;font-size:16px;display:inline-block;">
              Reset Password
            </a>
          </div>
          <p style="color:#6b7280;font-size:13px;margin:24px 0 0;line-height:1.6;">
            Or paste this link in your browser:<br>
            <a href="{link}" style="color:#8b5cf6;word-break:break-all;">{link}</a>
          </p>
          <hr style="border:none;border-top:1px solid rgba(255,255,255,0.08);margin:24px 0;">
          <p style="color:#6b7280;font-size:12px;margin:0;">
            If you didn't request a password reset, you can safely ignore this email.
            Your password will not be changed.
          </p>
        </td></tr>
        <!-- Footer -->
        <tr><td align="center" style="padding-top:24px;">
          <p style="color:#4b5563;font-size:12px;margin:0;">
            © 2025 SS SPARK · AI Question Paper Analyzer
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    text = (
        f"Reset your SS SPARK password\n\n"
        f"We received a request to reset your password.\n\n"
        f"Click the link below to reset it:\n{link}\n\n"
        f"This link expires in 30 minutes.\n\n"
        f"If you didn't request this, you can safely ignore this email.\n\n"
        f"Thanks,\nThe SS SPARK Team"
    )

    result = await send_email(email, subject, html, text)
    if result:
        logger.info("[notification] Password reset email sent successfully to %s", email)
    else:
        logger.error("[notification] Failed to send password reset email to %s", email)
    return result


async def send_admin_notification_email(
    to_email: str,
    title: str,
    body: str,
) -> bool:
    """Send a platform announcement or notification from the admin."""
    import html as _html
    safe_title = _html.escape(title)
    safe_body = _html.escape(body).replace("\n", "<br>")

    subject = f"[SS SPARK] {title}"
    html_content = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0d0d1a;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0d0d1a;padding:40px 20px;">
    <tr><td align="center">
      <table width="600" style="max-width:600px;">
        <tr><td align="center" style="padding-bottom:32px;">
          <h1 style="color:#8b5cf6;font-size:28px;margin:0;">SS SPARK</h1>
        </td></tr>
        <tr><td style="background:#1a1a2e;border:1px solid rgba(255,255,255,0.1);
                        border-radius:16px;padding:32px;">
          <h2 style="color:#fff;margin:0 0 16px;">{safe_title}</h2>
          <p style="color:#cbd5e1;line-height:1.7;">{safe_body}</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""

    return await send_email(to_email, subject, html_content, body)
