from .models import SiteConfig


def site_config(request):
    return {'site_config': SiteConfig.get()}

# core/context_processors.py
from .services import CommonDashboardService

def sidebar_recent_items(request):
    if request.user.is_authenticated:
        return CommonDashboardService.get_context(request.user)
    return {}