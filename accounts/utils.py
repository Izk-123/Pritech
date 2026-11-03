# accounts/utils.py
"""
Helpers for outbound email + IP/UA extraction.

── CHANGED ──────────────────────────────────────────────────────────────────
``send_verification_email``
    * Supports ``resend=True`` — rotates the token and restarts the clock.
    * Supports ``base_url=`` — works from management commands with no request.
    * Returns the URL that was sent (useful for tests + logging).

``sync_allauth_email`` (NEW)
    Mirrors our verification state onto allauth's ``EmailAddress`` row so
    allauth's password-reset & social flows don't reject valid users.
"""

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from .models import EmailVerificationToken


# ---------------------------------------------------------------------------
# Email delivery
# ---------------------------------------------------------------------------
def send_verification_email(user, request=None, *, resend: bool = False,
                             base_url: str | None = None) -> str:
    """
    Send (or resend) the account verification email.

    Parameters
    ----------
    user      : target User, already created with ``is_active=False``.
    request   : current HttpRequest, or None (management command / cron).
    resend    : True rotates the token & restarts the 24-hour clock.
    base_url  : fallback scheme+host when ``request`` is None.

    Returns
    -------
    str : the verification URL that was emailed.
    """
    token_obj, created = EmailVerificationToken.objects.get_or_create(user=user)

    # First-time send uses the freshly-created token.
    # A resend rotates it so any old link is invalidated.
    if resend and not created:
        token_obj.refresh()

    path = reverse("verify_email", kwargs={"token": token_obj.token})

    if request is not None:
        verification_url = request.build_absolute_uri(path)
    elif base_url:
        verification_url = base_url.rstrip("/") + path
    else:
        site = Site.objects.get_current()
        scheme = "https" if not settings.DEBUG else "http"
        verification_url = f"{scheme}://{site.domain}{path}"

    first_name = user.first_name or user.email.split("@")[0]

    if resend:
        subject = "New verification link — Pritech"
        intro = (
            f"Hello {first_name},\n\n"
            "Here is a fresh verification link for your Pritech account. "
            "The previous link has been disabled.\n"
        )
    else:
        subject = "Verify your email — Pritech"
        intro = (
            f"Hello {first_name},\n\n"
            "Thanks for signing up to Pritech. To activate your account, "
            "please verify your email address by clicking the link below.\n"
        )

    message = (
        f"{intro}\n"
        f"{verification_url}\n\n"
        f"This link expires in 24 hours.\n\n"
        "If you did not create a Pritech account you can safely ignore this "
        "email — no account will be activated without clicking the link.\n\n"
        "— The Pritech team"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    return verification_url


# ---------------------------------------------------------------------------
# allauth consistency (NEW)
# ---------------------------------------------------------------------------
def sync_allauth_email(user, verified: bool = True):
    """
    Keep allauth's ``EmailAddress`` row aligned with our own verification
    state. Called whenever a user transitions to is_active=True.

    allauth's password-reset view (and others we may enable later) checks
    ``EmailAddress.verified``; without this mirror, valid users can be
    rejected by allauth flows.
    """
    try:
        from allauth.account.models import EmailAddress
    except ImportError:
        return None

    obj, _ = EmailAddress.objects.update_or_create(
        user=user,
        email=user.email,
        defaults={"verified": verified, "primary": True},
    )
    return obj


# ---------------------------------------------------------------------------
# Existing helpers
# ---------------------------------------------------------------------------
def get_client_ip(request):
    """Extract client IP from request (honours X-Forwarded-For)."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def get_user_agent(request):
    """Return user agent string, truncated to a safe length."""
    return request.META.get("HTTP_USER_AGENT", "")[:500]


def parse_device(user_agent):
    """Simple device parser (Desktop/Mobile/Tablet)."""
    ua = (user_agent or "").lower()
    if "mobile" in ua or "android" in ua or "iphone" in ua:
        return "Mobile"
    elif "tablet" in ua or "ipad" in ua:
        return "Tablet"
    else:
        return "Desktop"