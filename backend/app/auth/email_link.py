"""
Passwordless email login via magic links.

Flow:
  1. POST /auth/email/request-login {"email": "..."} → backend mints a
     short-lived signed token, emails a click-to-login link, returns 200
     with a generic message (doesn't disclose whether the email exists).
  2. User clicks the link in their inbox →
     GET /auth/email/verify?token=... → backend verifies the token,
     find-or-creates the User row, mints a session JWT, redirects to
     {frontend_url}/#access_token=<jwt>.

Why this matters: works for any email provider (Gmail, Outlook, custom
domain, anything that accepts mail). No OAuth tenant restrictions. No
password to store, reset, or breach. The only dependency is the ACS
Email pipeline already configured.

Security model:
  - Tokens are JWTs signed with JWT_SECRET (no DB lookup needed for
    verification — short TTL is the protection).
  - 15-min TTL is short enough that link-replay attacks have a tiny
    window; long enough that real users can finish reading the email.
  - The `purpose: "login"` claim differentiates these from session
    JWTs so a leaked session token can't be reused as a magic link.
  - `aud` is fixed to "email-login" — session JWTs use
    "tech-intel-news-api" so accidental cross-use fails validation.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings
from app.integrations.email import send_digest as send_via_acs

log = logging.getLogger(__name__)

_LOGIN_TOKEN_TTL_MINUTES = 15
_LOGIN_TOKEN_AUDIENCE = "email-login"
_LOGIN_TOKEN_PURPOSE = "login"
_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class EmailIdentity:
    """Resolved identity from a successfully verified magic link."""
    oid: str          # stable per-email ID — sha256(email lowercased)
    tid: str          # sentinel "email" so the existing entra_tid column has a value
    email: str        # the verified email address
    display_name: str | None = None


def is_valid_email(email: str) -> bool:
    """Cheap RFC-ish check — rejects obvious garbage without blocking real mail."""
    return bool(_EMAIL_REGEX.match(email))


def _email_to_oid(email: str) -> str:
    """Stable per-email ID. Lowercased so case-different inputs collapse to one user."""
    digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()
    return f"email:{digest[:32]}"


def generate_login_token(email: str) -> str:
    """Mint a short-lived JWT carrying the email address."""
    now = datetime.now(timezone.utc)
    payload = {
        "iss": settings.jwt_issuer,
        "aud": _LOGIN_TOKEN_AUDIENCE,
        "purpose": _LOGIN_TOKEN_PURPOSE,
        "email": email.strip().lower(),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=_LOGIN_TOKEN_TTL_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_login_token(token: str) -> EmailIdentity:
    """
    Verify a magic-link token and return the resolved identity.

    Raises ValueError on any failure (bad signature, expired, wrong
    audience/purpose) — caller maps to a 400 response.
    """
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=_LOGIN_TOKEN_AUDIENCE,
            issuer=settings.jwt_issuer,
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("Login link has expired — request a new one")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid login link: {e}") from e

    if claims.get("purpose") != _LOGIN_TOKEN_PURPOSE:
        raise ValueError("Token is not a login token")

    email = claims.get("email")
    if not email or not is_valid_email(email):
        raise ValueError("Login token missing or has invalid email claim")

    return EmailIdentity(
        oid=_email_to_oid(email),
        tid="email",
        email=email,
        display_name=None,
    )


def send_login_email(*, to_email: str, login_url: str) -> bool:
    """
    Email the magic link to the user. Re-uses the ACS Email pipeline.

    Returns True on accepted send, False on any failure. We return True
    to the API caller even on False here, so attackers can't probe which
    emails exist by timing the response — but we log failures so real
    delivery problems are visible.
    """
    subject = "Sign in to Tech Intelligence News"
    html = (
        "<p>Click the link below to finish signing in. The link expires "
        f"in {_LOGIN_TOKEN_TTL_MINUTES} minutes.</p>"
        f'<p><a href="{login_url}">Sign in</a></p>'
        f'<p>Or paste this URL into your browser:<br>{login_url}</p>'
        "<p>If you didn't request this, you can ignore the email.</p>"
    )
    return send_via_acs(to_email=to_email, subject=subject, html=html)


def build_login_url(token: str) -> str:
    """
    Build the click-to-login URL the user receives in the email.

    Derives the backend's base URL from the configured oauth_redirect_uri
    (which is set deterministically in the Container App env). This avoids
    a separate `backend_base_url` setting.
    """
    base = settings.oauth_redirect_uri.rsplit("/api/", 1)[0]
    return f"{base}/api/v1/auth/email/verify?token={token}"
