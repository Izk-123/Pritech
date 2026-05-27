import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pritech.settings')
app = Celery('pritech')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()