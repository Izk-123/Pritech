"""
Decorators for permission/role enforcement on function-based views.
For CBVs use core.mixins.RoleRequiredMixin / PermissionRequiredMixin.
"""
from functools import wraps
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required


def role_required(*roles):
    """@role_required('ADMIN', 'FINANCE')"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not any(request.user.has_role(r) for r in roles):
                return HttpResponseForbidden(
                    '<h2 style="font-family:sans-serif;padding:2rem;">403 — Access denied.</h2>'
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def permission_required(perm_code):
    """@permission_required('can_generate_reports')"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not request.user.has_perm_code(perm_code):
                return HttpResponseForbidden(
                    '<h2 style="font-family:sans-serif;padding:2rem;">403 — Permission denied.</h2>'
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
