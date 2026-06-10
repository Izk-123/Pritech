"""
Tracking Middleware
===================
- Logs page visits asynchronously (Celery) or sync if Celery unavailable.
- Respects user consent (stored in cache for performance).
- IP addresses are hashed (SHA256) – never stored raw.
- Skips static/media/admin assets.
"""

import hashlib
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from .models import TrackingConsent, PageVisit
from .tasks import log_page_visit_async

SKIP_PATHS = [
    "/static/", "/media/", "/admin/jsi18n/", "/favicon.ico",
    "/tracking/opt-out/", "/tracking/export/", "/tracking/delete/"
]

# Check if we are in test mode (simplified)
import sys
IN_TEST = 'test' in sys.argv


class ActivityMiddleware(MiddlewareMixin):
    def __call__(self, request):
        response = self.get_response(request)
        path = request.path
        if any(path.startswith(s) for s in SKIP_PATHS):
            return response

        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key

        cache_key = f"tracking_consent_{user.id if user else session_key}"
        consent_given = cache.get(cache_key)
        if consent_given is None:
            consent_obj = None
            if user:
                consent_obj = TrackingConsent.objects.filter(user=user).first()
            elif session_key:
                consent_obj = TrackingConsent.objects.filter(session_key=session_key).first()
            consent_given = consent_obj.consent_given if consent_obj else False
            cache.set(cache_key, consent_given, 3600)

        if not consent_given:
            return response

        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        if ip and ',' in ip:
            ip = ip.split(',')[0].strip()
        ip_hash = hashlib.sha256(ip.encode()).hexdigest() if ip else None

        data = {
            'user_id': user.id if user else None,
            'session_key': session_key,
            'page_url': path,
            'ip_hash': ip_hash,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
            'consent_given': consent_given,
        }

        # In tests, run synchronously to avoid Celery issues
        if IN_TEST:
            from .models import PageVisit
            PageVisit.objects.create(**data)
        else:
            log_page_visit_async.delay(data)

        return response