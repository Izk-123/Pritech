"""
Portfolio App Tests
===================
Coverage for:
- Homepage rendering
- Inquiry form (valid submission, honeypot spam protection)
- Newsletter subscription (double opt‑in, confirmation, unsubscribe)
- GDPR data export and deletion
- Cache invalidation when services/projects change
- Graceful handling of empty database (no services)
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from unittest.mock import patch

from .models import (
    Inquiry,
    NewsletterSubscriber,
    PortfolioSettings,
    PortfolioProject,
)
from services.models import Service, ServiceCategory


class PortfolioTests(TestCase):
    """Main test suite for the portfolio app."""

    def setUp(self):
        """Set up test environment before each test."""
        self.client = Client()
        # Ensure singleton settings exist
        PortfolioSettings.get()
        # Clear any cached data from previous tests
        cache.clear()

    # -------------------------------------------------------------------------
    # Homepage and basic rendering
    # -------------------------------------------------------------------------

    def test_homepage_loads(self):
        """Test that the homepage returns 200 and uses the correct template."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "portfolio/home.html")
        self.assertIn("inquiry_form", response.context)
        self.assertIn("newsletter_form", response.context)

    # -------------------------------------------------------------------------
    # Inquiry form tests
    # -------------------------------------------------------------------------

    def test_inquiry_form_valid(self):
        """Test submitting a valid inquiry form."""
        data = {
            "name": "Test User",
            "email": "test@example.com",
            "subject": "Test Subject",
            "message": "Hello world",
            "honeypot": "",  # empty = not spam
        }
        response = self.client.post(reverse("home"), data)
        # Successful POST should redirect to same page (success_url = "/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Inquiry.objects.count(), 1)
        inquiry = Inquiry.objects.first()
        self.assertEqual(inquiry.name, "Test User")
        # Check that admin email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Pritech Inquiry", mail.outbox[0].subject)
        self.assertIn("test@example.com", mail.outbox[0].body)

    def test_inquiry_form_honeypot_spam(self):
        """Test that a submission with a filled honeypot field is rejected as spam."""
        data = {
            "name": "Spammer",
            "email": "spam@example.com",
            "subject": "Spam",
            "message": "Buy now",
            "honeypot": "filled",  # spam trap triggered
        }
        response = self.client.post(reverse("home"), data)
        # Form invalid -> re-renders page with status 200
        self.assertEqual(response.status_code, 200)
        # No inquiry should be saved
        self.assertEqual(Inquiry.objects.count(), 0)
        # Check that the form has a honeypot error
        form = response.context["inquiry_form"]
        self.assertTrue(form.errors)
        self.assertIn("honeypot", form.errors)
        self.assertEqual(form.errors["honeypot"][0], "Spam detected.")

    # -------------------------------------------------------------------------
    # Newsletter subscription (double opt‑in)
    # -------------------------------------------------------------------------

    def test_newsletter_subscribe_confirmation_email(self):
        """Test that subscribing sends a confirmation email and creates an unconfirmed subscriber."""
        data = {"email": "new@example.com", "consent": True}
        response = self.client.post(reverse("newsletter_subscribe"), data)
        # Should redirect back to home
        self.assertEqual(response.status_code, 302)
        self.assertEqual(NewsletterSubscriber.objects.count(), 1)
        sub = NewsletterSubscriber.objects.first()
        self.assertFalse(sub.is_confirmed)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Confirm your subscription", mail.outbox[0].subject)
        self.assertIn(str(sub.confirmation_token), mail.outbox[0].body)

    def test_newsletter_confirm(self):
        """Test that clicking the confirmation link marks the subscriber as confirmed."""
        sub = NewsletterSubscriber.objects.create(
            email="confirm@example.com",
            is_confirmed=False,
            consent_given=True,
        )
        url = reverse("newsletter_confirm", args=[sub.confirmation_token])
        response = self.client.get(url)
        sub.refresh_from_db()
        self.assertTrue(sub.is_confirmed)
        self.assertIsNotNone(sub.confirmed_at)
        # Admin email notification should be sent on confirmation
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("New newsletter subscriber", mail.outbox[0].subject)
        # Should redirect to home
        self.assertRedirects(response, reverse("home"))

    def test_newsletter_unsubscribe(self):
        """Test that unsubscribing sets the unsubscribed_at timestamp."""
        sub = NewsletterSubscriber.objects.create(
            email="unsub@example.com",
            is_confirmed=True,
            consent_given=True,
        )
        url = reverse("newsletter_unsubscribe", args=[sub.confirmation_token])
        response = self.client.get(url)
        sub.refresh_from_db()
        self.assertIsNotNone(sub.unsubscribed_at)
        self.assertRedirects(response, reverse("home"))

    # -------------------------------------------------------------------------
    # GDPR compliance: data export and deletion
    # -------------------------------------------------------------------------

    def test_gdpr_data_export(self):
        """Test that a user can export their data as JSON."""
        sub = NewsletterSubscriber.objects.create(
            email="gdpr@example.com",
            is_confirmed=True,
            consent_given=True,
            consent_ip="127.0.0.1",
            ip_address="127.0.0.1",
        )
        response = self.client.post(reverse("gdpr_export"), {"email": "gdpr@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn(b"gdpr@example.com", response.content)
        self.assertIn(b"consent_given", response.content)

    def test_gdpr_data_deletion(self):
        """Test that a user can request deletion of their data."""
        sub = NewsletterSubscriber.objects.create(email="delete@example.com")
        response = self.client.post(reverse("gdpr_delete"), {"email": "delete@example.com"})
        self.assertRedirects(response, reverse("home"))
        self.assertFalse(NewsletterSubscriber.objects.filter(email="delete@example.com").exists())

    # -------------------------------------------------------------------------
    # Cache invalidation
    # -------------------------------------------------------------------------

    def test_cache_invalidation_on_service_change(self):
        """Test that adding/changing a service clears the homepage cache."""
        # First request populates cache
        response = self.client.get(reverse("home"))
        self.assertIsNotNone(cache.get("active_services"))

        # Create a new service – this should trigger cache invalidation
        category = ServiceCategory.objects.create(name="Test Cat")
        service = Service.objects.create(name="Test Service", category=category)
        # After saving, the cache should be cleared
        self.assertIsNone(cache.get("active_services"))

    # -------------------------------------------------------------------------
    # Edge cases: empty database
    # -------------------------------------------------------------------------

    def test_empty_database_handling(self):
        """Test that the homepage handles missing services/projects gracefully."""
        # Delete all services and projects
        Service.objects.all().delete()
        PortfolioProject.objects.all().delete()
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        # Check that the empty state message is displayed
        self.assertContains(response, "Our service catalogue is being updated")
        # The services grid should be empty
        self.assertNotContains(response, "service-card")