from django.contrib.auth.signals import user_logged_in, user_login_failed, user_logged_out
from django.dispatch import receiver
from .models import UserAuditLog


def _get_ip(request):
    if not request:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', None)


def _get_ua(request):
    if not request:
        return ''
    return request.META.get('HTTP_USER_AGENT', '')[:500]


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    UserAuditLog.objects.create(
        user=user,
        action='login_success',
        ip_address=_get_ip(request),
        user_agent=_get_ua(request),
    )


@receiver(user_login_failed)
def log_login_failed(sender, request, credentials, **kwargs):
    UserAuditLog.objects.create(
        user=None,
        action=f"login_failed:{credentials.get('username', '')}",
        ip_address=_get_ip(request),
        user_agent=_get_ua(request),
    )


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    if user:
        UserAuditLog.objects.create(
            user=user,
            action='logout',
            ip_address=_get_ip(request),
            user_agent=_get_ua(request),
        )
