# core/context_processors.py
from .models import SiteConfig
from finance.models import Expense   # new import

def site_config(request):
    return {'site_config': SiteConfig.get()}

def sidebar_recent_items(request):
    if request.user.is_authenticated:
        from .services import CommonDashboardService
        return CommonDashboardService.get_context(request.user)
    return {}

def pending_expenses_count(request):
    """Provide count of pending expenses for staff users (used in sidebar badge)."""
    if request.user.is_authenticated and request.user.is_staff:
        try:
            count = Expense.objects.filter(status='pending').count()
            return {'pending_expenses_count': count}
        except Exception:
            return {'pending_expenses_count': 0}
    return {}