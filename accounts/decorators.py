# accounts/decorators.py
from functools import wraps
from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.shortcuts import redirect


def rate_limit(key_func, rate='5/h', method='POST', block=True):
    """
    Custom rate limiter using Django's cache.
    rate format: 'count/period' where period = 's' (seconds), 'm' (minutes), 'h' (hours), 'd' (days)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.method != method:
                return view_func(request, *args, **kwargs)

            # Parse rate
            count_str, period_char = rate.split('/')
            count = int(count_str)
            if period_char == 's':
                seconds = 1
            elif period_char == 'm':
                seconds = 60
            elif period_char == 'h':
                seconds = 3600
            elif period_char == 'd':
                seconds = 86400
            else:
                seconds = 3600  # default hour

            # Get cache key
            key = key_func(request)
            cache_key = f"rate_limit:{key}"

            # Get current count
            current = cache.get(cache_key, 0)
            if current >= count:
                if block:
                    return HttpResponseForbidden("Rate limit exceeded. Please try again later.")
                else:
                    return view_func(request, *args, **kwargs)

            # Increment and set expiry
            cache.set(cache_key, current + 1, timeout=seconds)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def client_role_required(allowed_roles):
    """
    Decorator to restrict access to client views based on client_role.
    allowed_roles: list of roles (e.g., ['admin', 'billing'])
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if request.user.user_type != 'client':
                return HttpResponseForbidden("Access denied.")
            if request.user.client_role not in allowed_roles:
                return HttpResponseForbidden("You do not have permission for this action.")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator