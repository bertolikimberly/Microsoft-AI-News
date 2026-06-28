"""
Email delivery via Azure Communication Services (ACS).

Configuration (in backend/.env):
  ACS_CONNECTION_STRING  — primary connection string from
                           Azure Portal → mainews-comms2026 → Settings → Keys
  ACS_SENDER_ADDRESS     — MailFrom address from the verified ACS domain,
                           e.g. DoNotReply@<random>.azurecomm.net

Failure handling: missing credentials or ACS errors are logged and return
False — the worker keeps going for other users instead of crashing the run.
"""
from __future__ import annotations

import logging

from azure.communication.email import EmailClient

from app.config import settings

log = logging.getLogger(__name__)


def is_configured() -> bool:
    """True if ACS credentials are present."""
    return bool(settings.acs_connection_string and settings.acs_sender_address)


def send_digest(
    *,
    to_email: str,
    subject: str,
    html: str,
) -> bool:
    """
    Send one transactional email via ACS.
    Returns True on success, False on any failure. Never raises.
    """
    if not is_configured():
        log.info(
            "email.send_digest: ACS_CONNECTION_STRING or ACS_SENDER_ADDRESS not set "
            "— skipping send to %s",
            to_email,
        )
        return False

    try:
        client = EmailClient.from_connection_string(settings.acs_connection_string)
        message = {
            "senderAddress": settings.acs_sender_address,
            "recipients": {"to": [{"address": to_email}]},
            "content": {"subject": subject, "html": html},
        }
        poller = client.begin_send(message)
        poller.result()
        log.info("email.send_digest: sent to %s", to_email)
        return True
    except Exception as exc:
        log.warning("email.send_digest: ACS error sending to %s: %s", to_email, exc)
        return False
