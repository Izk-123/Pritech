"""
Tracking Async Tasks (optional Celery)
If Celery is not configured, tasks run synchronously.
"""

import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Try to import Celery, but fallback gracefully if not installed/configured
try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    # Define a dummy decorator
    def shared_task(func):
        return func


if CELERY_AVAILABLE:
    @shared_task
    def log_page_visit_async(data):
        from .models import PageVisit
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user_id = data.pop('user_id', None)
        user = User.objects.filter(pk=user_id).first() if user_id else None
        PageVisit.objects.create(user=user, **data)
else:
    # Synchronous fallback
    def log_page_visit_async(data):
        from .models import PageVisit
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user_id = data.pop('user_id', None)
        user = User.objects.filter(pk=user_id).first() if user_id else None
        PageVisit.objects.create(user=user, **data)
        
@shared_task
def cleanup_tracking_data():
    from django.core.management import call_command
    call_command("cleanup_tracking", days=30)