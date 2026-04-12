from .models import PageVisit

SKIP_PATHS = ['/static/', '/media/', '/admin/jsi18n/', '/favicon.ico']


class ActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path
        if not any(path.startswith(s) for s in SKIP_PATHS):
            try:
                ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
                PageVisit.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    page_url=path,
                    ip_address=ip.split(',')[0].strip() if ip else None,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                )
            except Exception:
                pass
        return response
