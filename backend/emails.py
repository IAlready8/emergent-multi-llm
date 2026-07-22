"""Resend email helper."""
from __future__ import annotations

import asyncio
import logging
import os

import resend

logger = logging.getLogger(__name__)

resend.api_key = os.environ.get("RESEND_API_KEY", "")
SENDER = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")


async def send_email(to: str, subject: str, html: str) -> bool:
    if not resend.api_key:
        logger.warning("RESEND_API_KEY missing; email not sent")
        return False
    try:
        params = {"from": SENDER, "to": [to], "subject": subject, "html": html}
        await asyncio.to_thread(resend.Emails.send, params)
        return True
    except Exception as e:
        logger.error("resend failed: %s", e)
        return False


def password_reset_html(reset_link: str) -> str:
    return f"""
    <table width="100%" style="font-family:Inter,Arial,sans-serif;background:#09090b;padding:32px;color:#fafafa">
      <tr><td>
        <h1 style="margin:0 0 12px 0;color:#f59e0b">Prometheus</h1>
        <p style="color:#a1a1aa">You requested a password reset.</p>
        <p><a href="{reset_link}" style="display:inline-block;padding:12px 20px;background:#f59e0b;color:#09090b;font-weight:600;text-decoration:none;border-radius:6px">Reset Password</a></p>
        <p style="color:#71717a;font-size:12px">If you did not request this, ignore this email. Link expires in 1 hour.</p>
      </td></tr>
    </table>
    """
