from django.http import HttpResponseForbidden, JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect


class RoleRequiredMixin(LoginRequiredMixin):
    """Restrict a view to users who hold at least one of required_roles."""
    required_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if self.required_roles:
            if not any(request.user.has_role(r) for r in self.required_roles):
                if request.headers.get('HX-Request'):
                    return JsonResponse({'error': 'Permission denied'}, status=403)
                return HttpResponseForbidden(
                    '<h2 style="font-family:sans-serif;padding:2rem;">403 — You do not have permission to access this page.</h2>'
                )
        return super().dispatch(request, *args, **kwargs)


class PermissionRequiredMixin(LoginRequiredMixin):
    """Restrict a view to users who hold a specific permission code."""
    permission_required = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if self.permission_required:
            if not request.user.has_perm_code(self.permission_required):
                if request.headers.get('HX-Request'):
                    return JsonResponse({'error': 'Permission denied'}, status=403)
                return HttpResponseForbidden(
                    '<h2 style="font-family:sans-serif;padding:2rem;">403 — Permission denied.</h2>'
                )
        return super().dispatch(request, *args, **kwargs)


class HtmxMixin:
    """Helpers for HTMX-powered views."""

    def is_htmx(self):
        return bool(self.request.headers.get('HX-Request'))

    def htmx_redirect(self, url):
        response = HttpResponseForbidden()
        response['HX-Redirect'] = url
        response.status_code = 200
        return response
