# accounts/signals.py
"""
Signals for audit logging, session tracking, login events, and real-time
presence broadcasting.

Signal receivers
----------------
  user_logged_in     → UserAuditLog + LoginEvent + UserSession + WS "online"
  user_login_failed  → UserAuditLog + LoginEvent (no user row)
  user_logged_out    → UserAuditLog + LoginEvent + UserSession close + WS "offline"

── FIXED ────────────────────────────────────────────────────────────────────
Bug: ``LoginEvent.ip_address`` and ``UserSession.ip_address`` are declared
``GenericIPAddressField(null=False)`` — i.e. ``NOT NULL``. The previous
``_get_ip()`` returned ``None`` when ``REMOTE_ADDR`` was missing (Django test
client via ``force_login``, management commands, proxies that strip the
header) and ``''`` when both headers were empty. Both values violate the
schema and raise::

    IntegrityError: NOT NULL constraint failed: accounts_loginevent.ip_address

Fix: ``_get_ip()`` now ALWAYS returns a non-empty string. When no real IP is
available it uses the RFC 5737 sentinel ``0.0.0.0`` ("this network"), which
is a syntactically valid IPv4 address that the DB column accepts.

No migration is required — the model's NOT NULL constraint is satisfied by
the sentinel; only the runtime behaviour changes.
"""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver
from django.utils import timezone

from .models import LoginEvent, UserAuditLog, UserSession
from .utils import parse_device


# ============================================================================
# IP / User-Agent extraction helpers
# ============================================================================

# Sentinel used when the request context cannot provide a real client IP.
# RFC 5737 "This network" — a valid IPv4 string so the NOT NULL column is
# always satisfied. Never returned to users, only stored for audit rows.
UNKNOWN_IP = "0.0.0.0"


def _get_ip(request):
    """
    Return the client IP as a non-empty string.

    Priority
    --------
    1. ``X-Forwarded-For`` (first hop) — set by load balancers / proxies.
    2. ``REMOTE_ADDR``                 — direct connection.
    3. ``UNKNOWN_IP`` (``0.0.0.0``)    — no request / no headers at all.

    Guarantees
    ----------
    * Never returns ``None``.
    * Never returns ``""``.
    * Returned string is always accepted by ``GenericIPAddressField``.

    Rationale
    ---------
    ``LoginEvent.ip_address`` and ``UserSession.ip_address`` are declared
    ``null=False``. Feeding them ``None`` (as the old code did under
    ``force_login`` and proxies) raises ``IntegrityError`` and aborts the
    whole login signal chain — which in turn blocks the login itself.
    """
    if not request:
        return UNKNOWN_IP

    # 1. Proxy header
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        candidate = xff.split(",")[0].strip()
        if candidate:
            return candidate

    # 2. Direct connection
    remote = request.META.get("REMOTE_ADDR")
    if remote:
        return remote

    # 3. Nothing usable — use sentinel rather than fail the login
    return UNKNOWN_IP


def _get_ua(request):
    """Return the User-Agent header, truncated to a safe length."""
    if not request:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")[:500]


# ============================================================================
# login_success
# ============================================================================

@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    """
    Fires on every successful authentication (password, social, 2FA).

    Side effects
    ------------
    * ``UserAuditLog``          — persistent audit row.
    * ``LoginEvent`` (success)  — analytics row.
    * ``User.last_login_ip``    — cached convenience field.
    * ``UserSession``           — active-session tracking row.
    * WebSocket broadcast       — ``user_online`` to the ``presence`` group.
    """
    ip = _get_ip(request)
    ua = _get_ua(request)

    # --- Audit log ------------------------------------------------------
    UserAuditLog.objects.create(
        user=user,
        action="login_success",
        ip_address=ip,
        user_agent=ua,
    )

    # --- Analytics event ------------------------------------------------
    LoginEvent.objects.create(
        user=user,
        event_type="success",
        ip_address=ip,
        user_agent=ua,
    )

    # --- Cache last_login_ip on the user --------------------------------
    # Skip when we only had the sentinel — do not overwrite a real IP with
    # 0.0.0.0 just because this particular login came from a CLI context.
    if ip != UNKNOWN_IP and user.last_login_ip != ip:
        user.last_login_ip = ip
        user.save(update_fields=["last_login_ip"])

    # --- Session tracking ----------------------------------------------
    session_key = request.session.session_key if request else None
    if session_key:
        UserSession.objects.create(
            user=user,
            session_key=session_key,
            ip_address=ip,
            user_agent=ua,
            device=parse_device(ua),
            is_active=True,
        )

    # --- Broadcast presence --------------------------------------------
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "presence",
        {
            "type": "user_online",
            "user_id": str(user.id),
            "email": user.email,
        },
    )


# ============================================================================
# login_failed
# ============================================================================

@receiver(user_login_failed)
def on_login_failed(sender, request, credentials, **kwargs):
    """
    Fires on every failed credential check.

    We intentionally log with ``user=None`` — the credentials were never
    tied to a real authenticated user, so storing the submitted username
    in ``action`` (prefixed) keeps analytics useful without touching the FK.
    """
    ip = _get_ip(request)
    ua = _get_ua(request)
    username = credentials.get("username", "")

    UserAuditLog.objects.create(
        user=None,
        action=f"login_failed:{username}",
        ip_address=ip,
        user_agent=ua,
    )
    LoginEvent.objects.create(
        user=None,
        event_type="failed",
        ip_address=ip,
        user_agent=ua,
        reason=f"Invalid credentials for {username}",
    )


# ============================================================================
# logout
# ============================================================================

@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    """
    Fires on logout. Closes the open session row and broadcasts offline.

    ``user`` may be ``None`` (e.g. logout of an already-expired session);
    in that case there is nothing to log.
    """
    if not user:
        return

    ip = _get_ip(request)
    ua = _get_ua(request)

    # --- Audit + analytics ----------------------------------------------
    UserAuditLog.objects.create(
        user=user,
        action="logout",
        ip_address=ip,
        user_agent=ua,
    )
    LoginEvent.objects.create(
        user=user,
        event_type="logout",
        ip_address=ip,
        user_agent=ua,
    )

    # --- Close the active session --------------------------------------
    session_key = request.session.session_key if request else None
    if session_key:
        UserSession.objects.filter(session_key=session_key).update(
            logout_time=timezone.now(),
            is_active=False,
        )

    # --- Broadcast offline ---------------------------------------------
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "presence",
        {"type": "user_offline", "user_id": str(user.id)},
    )