import asyncio

import resend
from loguru import logger

from backend.config import backend_settings

resend.api_key = backend_settings.RESEND_API_KEY

_APPROVAL_SUBJECT = "Ta demande d'accès à Coupette a été approuvée"

_APPROVAL_HTML = """\
<p>Allo !</p>
<p>Ta demande d'accès à Coupette a été approuvée.</p>
<p>
  <a href="https://coupette.club/login"
     style="display:inline-block;padding:10px 20px;background:#c89248;color:#fff;
            text-decoration:none;border-radius:8px;font-weight:500;">
    Accéder à Coupette →
  </a>
</p>
<p>Santé !<br>Victor</p>
"""

_APPROVAL_TEXT = """\
Allo !

Ta demande d'accès à Coupette a été approuvée.

Accéder à Coupette : https://coupette.club/login

Santé !
Victor
"""


async def send_approval_email(email: str) -> None:
    """Send the waitlist approval email via Resend.

    No-ops if RESEND_API_KEY is not configured (dev / CI).
    Raises on Resend errors — caller decides whether to swallow or propagate.
    """
    if not backend_settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping approval email to {}", email)
        return

    params: resend.Emails.SendParams = {
        "from": backend_settings.RESEND_FROM_EMAIL,
        "to": [email],
        "subject": _APPROVAL_SUBJECT,
        "html": _APPROVAL_HTML,
        "text": _APPROVAL_TEXT,
    }

    await asyncio.get_running_loop().run_in_executor(None, resend.Emails.send, params)
