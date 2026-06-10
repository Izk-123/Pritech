"""
Tracking App Models
===================
- TrackingConsent: stores user/session consent for GDPR compliance.
- PageVisit: anonymised page view logs (IP hashed, never stored raw).
- UserActivity: anonymised audit of user actions (login, logout, etc.).
All models have indexes for performance and simple_history for audit.
"""

from django.db import models
from django.conf import settings
from simple_history.models import HistoricalRecords
import hashlib


class TrackingConsent(models.Model):
    """
    Records whether a user (or anonymous session) has consented to tracking.
    Used to comply with GDPR/ePrivacy.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tracking_consent",
    )
    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    consent_given = models.BooleanField(default=False)
    consent_ip = models.GenericIPAddressField(null=True, blank=True)  # last IP when consent given
    consented_at = models.DateTimeField(auto_now_add=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        indexes = [models.Index(fields=["session_key"])]

    def __str__(self):
        return f"Consent for {self.user or self.session_key}: {self.consent_given}"


class PageVisit(models.Model):
    """
    Anonymised page view record. Original IP is never stored – only a SHA256 hash.
    Useful for analytics without violating privacy.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_index=True,
    )
    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    page_url = models.CharField(max_length=500, db_index=True)
    ip_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA256 hash of the client IP address (never raw IP)",
    )
    user_agent = models.CharField(max_length=500, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    consent_given = models.BooleanField(default=False)  # snapshot at time of visit
    history = HistoricalRecords()  # audit trail

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["timestamp"]),
            models.Index(fields=["page_url"]),
            models.Index(fields=["user", "timestamp"]),
        ]

    @staticmethod
    def anonymise_ip(ip):
        """Return SHA256 hash of IP (or None if IP is empty)."""
        if not ip:
            return None
        return hashlib.sha256(ip.encode()).hexdigest()

    def __str__(self):
        return f"{self.page_url} – {self.timestamp}"


class UserActivity(models.Model):
    """
    Anonymised user action log (login, logout, etc.).
    IP addresses are hashed identically to PageVisit.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_index=True,
    )
    action = models.CharField(max_length=255, db_index=True)
    ip_hash = models.CharField(max_length=64, help_text="SHA256 hash of IP address")
    user_agent = models.CharField(max_length=500, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-timestamp"]
        verbose_name_plural = "User activities"
        indexes = [
            models.Index(fields=["timestamp"]),
            models.Index(fields=["user", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.user} – {self.action} at {self.timestamp}"