"""
Tracking App Tests – Final Working Version
"""

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import hashlib
from unittest.mock import patch

from tracking.models import TrackingConsent, PageVisit, UserActivity

User = get_user_model()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class TrackingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="pass",
            user_type="client"
        )
        self.client.login(email="test@example.com", password="pass")
        cache.clear()

    # -------------------------------------------------------------------------
    # Basic consent & logging
    # -------------------------------------------------------------------------

    def test_consent_required_for_logging(self):
        self.client.get("/")
        self.assertEqual(PageVisit.objects.count(), 0)

    def test_consent_given_logs_visits(self):
        TrackingConsent.objects.create(user=self.user, consent_given=True)
        self.client.get("/")
        self.assertEqual(PageVisit.objects.count(), 1)
        visit = PageVisit.objects.first()
        self.assertEqual(visit.user, self.user)
        self.assertTrue(visit.consent_given)

    def test_ip_anonymisation(self):
        ip = "192.168.1.1"
        expected = hashlib.sha256(ip.encode()).hexdigest()
        self.assertEqual(PageVisit.anonymise_ip(ip), expected)
        self.assertIsNone(PageVisit.anonymise_ip(""))

    def test_opt_out_view(self):
        consent = TrackingConsent.objects.create(user=self.user, consent_given=True)
        response = self.client.post(reverse("tracking_opt_out"))
        self.assertRedirects(response, reverse("home"))
        consent.refresh_from_db()
        self.assertFalse(consent.consent_given)
        self.assertIsNotNone(consent.withdrawn_at)

    # -------------------------------------------------------------------------
    # GDPR data export / deletion
    # -------------------------------------------------------------------------

    def test_gdpr_export(self):
        TrackingConsent.objects.create(user=self.user, consent_given=True)
        PageVisit.objects.create(user=self.user, page_url="/test", ip_hash="xxx", consent_given=True)
        response = self.client.get(reverse("tracking_data_export"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn(b"page_visits", response.content)

    def test_gdpr_delete(self):
        TrackingConsent.objects.create(user=self.user, consent_given=True)
        user = User.objects.get(pk=self.user.pk)
        PageVisit.objects.create(user=user, page_url="/test", ip_hash="xxx")
        self.assertEqual(PageVisit.objects.count(), 1)
        # follow=False prevents assertRedirects from making a GET to /profile/,
        # which would trigger ActivityMiddleware to log a new PageVisit.
        response = self.client.post(reverse("tracking_data_delete"), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("profile"), response["Location"])
        # Only the /test visit should be gone
        self.assertEqual(PageVisit.objects.filter(page_url="/test").count(), 0)

    # -------------------------------------------------------------------------
    # Cleanup management command
    # -------------------------------------------------------------------------

    def test_cleanup_command(self):
        from django.core.management import call_command

        # Use a fixed, far‑past timestamp (no timezone issues)
        old_time = timezone.datetime(2023, 1, 1, 0, 0, 0)
        old_time = timezone.make_aware(old_time, timezone.get_current_timezone())
        old_visit = PageVisit.objects.create(
            user=self.user, page_url="/old", ip_hash="xxx", consent_given=True
        )
        # auto_now_add ignores values passed to create(); use update() to backdate
        PageVisit.objects.filter(pk=old_visit.pk).update(timestamp=old_time)

        PageVisit.objects.create(
            user=self.user, page_url="/new", ip_hash="xxx", consent_given=True
        )

        call_command("cleanup_tracking", days=30)
        # Only the new record should remain
        self.assertEqual(PageVisit.objects.count(), 1)
        self.assertEqual(PageVisit.objects.first().page_url, "/new")

    def test_cleanup_anonymise_only(self):
        from django.core.management import call_command

        old_time = timezone.datetime(2023, 1, 1, 0, 0, 0)
        old_time = timezone.make_aware(old_time, timezone.get_current_timezone())
        old_visit = PageVisit.objects.create(
            user=self.user, page_url="/old", ip_hash="original", consent_given=True
        )
        # auto_now_add ignores values passed to create(); use update() to backdate
        PageVisit.objects.filter(pk=old_visit.pk).update(timestamp=old_time)

        call_command("cleanup_tracking", days=30, anonymise_only=True)
        visit = PageVisit.objects.get(page_url="/old")
        self.assertEqual(visit.ip_hash, "anonymised")

    # -------------------------------------------------------------------------
    # Staff dashboard
    # -------------------------------------------------------------------------

    def test_tracking_dashboard_staff_only(self):
        response = self.client.get(reverse("tracking_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.user.is_staff = True
        self.user.save()
        response = self.client.get(reverse("tracking_dashboard"))
        self.assertEqual(response.status_code, 200)