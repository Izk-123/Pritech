"""
Management command to delete or anonymise old tracking data.
Usage: python manage.py cleanup_tracking [--days N] [--anonymise-only]
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from tracking.models import PageVisit, UserActivity, TrackingConsent


class Command(BaseCommand):
    help = "Delete or anonymise tracking records older than N days"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--anonymise-only", action="store_true")

    def handle(self, *args, **options):
        days = options["days"]
        cutoff = timezone.now() - timedelta(days=days)
        anonymise_only = options["anonymise_only"]

        # Use datetime comparison (microsecond‑safe). Add a 1‑second buffer
        # to ensure records exactly `days` old are included.
        cutoff = cutoff - timedelta(seconds=1)

        if anonymise_only:
            page_count = PageVisit.objects.filter(timestamp__lt=cutoff, ip_hash__isnull=False).update(ip_hash="anonymised")
            activity_count = UserActivity.objects.filter(timestamp__lt=cutoff, ip_hash__isnull=False).update(ip_hash="anonymised")
            self.stdout.write(self.style.SUCCESS(
                f"Anonymised {page_count} page visits and {activity_count} activities older than {days} days."
            ))
        else:
            page_count, _ = PageVisit.objects.filter(timestamp__lt=cutoff).delete()
            activity_count, _ = UserActivity.objects.filter(timestamp__lt=cutoff).delete()
            consent_count, _ = TrackingConsent.objects.filter(withdrawn_at__lt=cutoff).delete()
            self.stdout.write(self.style.SUCCESS(
                f"Deleted {page_count} page visits, {activity_count} activities, and {consent_count} consent records older than {days} days."
            ))