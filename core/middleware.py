# core/middleware.py
from django.shortcuts import render
from .models import SiteConfig


class MaintenanceModeMiddleware:
    """Show maintenance page if SiteConfig.maintenance_mode is True (non‑staff only)."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        config = SiteConfig.get()
        if config.maintenance_mode:
            # Allow staff to bypass maintenance mode
            if request.user.is_authenticated and request.user.is_staff:
                return self.get_response(request)
            # Show maintenance page for all others
            return render(request, 'core/maintenance.html', status=503)
        return self.get_response(request)