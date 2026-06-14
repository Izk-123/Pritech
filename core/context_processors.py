# core/context_processors.py
"""
Global context processors for the Core app.
Available in all templates.
"""

from django.utils import timezone
from .models import SiteConfig, Announcement
from accounts.models import UserSession


def site_config(request):
    """Add the site configuration to every template."""
    return {'site_config': SiteConfig.get()}


def sidebar_recent_items(request):
    """Add recent tickets and invoices to the sidebar."""
    if request.user.is_authenticated:
        from .services import CommonDashboardService
        return CommonDashboardService.get_context(request.user)
    return {}


def pending_expenses_count(request):
    """Count of pending expenses for staff users (used in sidebar badge)."""
    if request.user.is_authenticated and request.user.is_staff:
        try:
            from finance.models import Expense
            count = Expense.objects.filter(status='pending').count()
            return {'pending_expenses_count': count}
        except Exception:
            return {'pending_expenses_count': 0}
    return {}


def announcements(request):
    """Current active announcements for the dashboard."""
    now = timezone.now()
    active = Announcement.objects.filter(is_active=True, start_date__lte=now, end_date__gte=now)
    return {'current_announcements': active}


def online_users_count(request):
    """Number of users active in the last 5 minutes (staff only)."""
    if request.user.is_authenticated and request.user.is_staff:
        threshold = timezone.now() - timezone.timedelta(minutes=5)
        count = UserSession.objects.filter(
            last_activity__gte=threshold, is_active=True
        ).values('user').distinct().count()
        return {'online_users_count': count}
    return {}