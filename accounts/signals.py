# accounts/signals.py
"""
Signals for audit logging, session tracking, login events, and real‑time presence.
"""

from django.contrib.auth.signals import user_logged_in, user_login_failed, user_logged_out
from django.dispatch import receiver
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import UserAuditLog, LoginEvent, UserSession
from .utils import get_client_ip, get_user_agent, parse_device


def _get_ip(request):
    if not request:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')


def _get_ua(request):
    if not request:
        return ''
    return request.META.get('HTTP_USER_AGENT', '')[:500]


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    """Create audit log, login event, session record, and broadcast online status."""
    ip = _get_ip(request)
    ua = _get_ua(request)

    # Audit log
    UserAuditLog.objects.create(
        user=user,
        action='login_success',
        ip_address=ip,
        user_agent=ua,
    )

    # Analytics event
    LoginEvent.objects.create(
        user=user,
        event_type='success',
        ip_address=ip,
        user_agent=ua,
    )

    # Update last_login_ip on user
    if ip and user.last_login_ip != ip:
        user.last_login_ip = ip
        user.save(update_fields=['last_login_ip'])

    # Session tracking
    session_key = request.session.session_key
    if session_key:
        device = parse_device(ua)
        UserSession.objects.create(
            user=user,
            session_key=session_key,
            ip_address=ip or '',
            user_agent=ua,
            device=device,
            is_active=True
        )

    # Real‑time presence via Channels
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "presence",
        {
            "type": "user_online",
            "user_id": str(user.id),
            "email": user.email
        }
    )


@receiver(user_login_failed)
def on_login_failed(sender, request, credentials, **kwargs):
    """Log failed login attempts."""
    ip = _get_ip(request)
    ua = _get_ua(request)
    username = credentials.get('username', '')

    UserAuditLog.objects.create(
        user=None,
        action=f"login_failed:{username}",
        ip_address=ip,
        user_agent=ua,
    )
    LoginEvent.objects.create(
        user=None,
        event_type='failed',
        ip_address=ip,
        user_agent=ua,
        reason=f"Invalid credentials for {username}"
    )


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    """Log logout, close session, and broadcast offline status."""
    if not user:
        return

    ip = _get_ip(request)
    ua = _get_ua(request)

    UserAuditLog.objects.create(
        user=user,
        action='logout',
        ip_address=ip,
        user_agent=ua,
    )
    LoginEvent.objects.create(
        user=user,
        event_type='logout',
        ip_address=ip,
        user_agent=ua,
    )

    # Close the session
    session_key = request.session.session_key
    if session_key:
        UserSession.objects.filter(session_key=session_key).update(logout_time=timezone.now(), is_active=False)

    # Broadcast offline
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "presence",
        {
            "type": "user_offline",
            "user_id": str(user.id)
        }
    )