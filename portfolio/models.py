"""
Portfolio App Models
====================
- PortfolioProject: Showcase work.
- Inquiry: Contact form submissions.
- NewsletterSubscriber: GDPR-compliant newsletter signups.
- PortfolioSettings: Singleton model for homepage content.
All models support audit logging (simple_history) and proper indexes.
"""

import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django_quill.fields import QuillField
from simple_history.models import HistoricalRecords
import bleach

# -----------------------------------------------------------------------------
# Custom QuillField that sanitizes HTML before saving (XSS prevention)
# -----------------------------------------------------------------------------

class SanitizingQuillField(QuillField):
    """
    Extends QuillField to automatically sanitize HTML content using bleach.
    Prevents XSS attacks from user-generated content (e.g., project descriptions).
    """
    def pre_save(self, model_instance, add):
        value = getattr(model_instance, self.attname)
        if value and isinstance(value, dict) and "html" in value:
            allowed_tags = [
                "p", "br", "strong", "b", "em", "i", "u", "a", "ul", "ol", "li",
                "h1", "h2", "h3", "h4", "h5", "h6", "pre", "code", "span"
            ]
            allowed_attrs = {"a": ["href", "title"], "span": ["class"]}
            value["html"] = bleach.clean(
                value["html"],
                tags=allowed_tags,
                attributes=allowed_attrs,
                strip=True,
            )
            setattr(model_instance, self.attname, value)
        return super().pre_save(model_instance, add)


# -----------------------------------------------------------------------------
# Portfolio Project
# -----------------------------------------------------------------------------

class PortfolioProject(models.Model):
    """A showcased project on the homepage portfolio section."""
    title = models.CharField(max_length=200)
    description = SanitizingQuillField(blank=True)  # Auto-sanitized
    image = models.ImageField(upload_to="portfolio/", null=True, blank=True)
    client_name = models.CharField(max_length=200, blank=True)
    technologies = models.CharField(max_length=300, blank=True)
    is_featured = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    history = HistoricalRecords()  # Audit log

    class Meta:
        ordering = ["order", "-pk"]

    def __str__(self):
        return self.title


# -----------------------------------------------------------------------------
# Inquiry (Contact Form)
# -----------------------------------------------------------------------------

class Inquiry(models.Model):
    """Contact form submission from public visitors."""
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^\+?[\d\s\-\(\)]{7,20}$",
                message="Enter a valid phone number (7-20 digits, optional +)."
            )
        ],
    )
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    history = HistoricalRecords()  # Audit log

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Inquiries"
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["is_read"]),
        ]

    def __str__(self):
        return f"{self.name} – {self.subject}"


# -----------------------------------------------------------------------------
# Newsletter Subscriber (GDPR compliant)
# -----------------------------------------------------------------------------

class NewsletterSubscriber(models.Model):
    """Email newsletter subscriber with double opt-in and consent tracking."""
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    is_confirmed = models.BooleanField(default=False)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    confirmation_token = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True
    )
    # Consent tracking (GDPR)
    consent_given = models.BooleanField(default=False)
    consent_ip = models.GenericIPAddressField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    history = HistoricalRecords()  # Audit log

    class Meta:
        ordering = ["-subscribed_at"]
        verbose_name = "Newsletter Subscriber"
        verbose_name_plural = "Newsletter Subscribers"
        indexes = [
            models.Index(fields=["subscribed_at"]),
            models.Index(fields=["is_confirmed"]),
        ]

    def __str__(self):
        return self.email

    def is_active(self):
        """Active = confirmed and not unsubscribed."""
        return self.is_confirmed and self.unsubscribed_at is None


# -----------------------------------------------------------------------------
# Portfolio Settings (Singleton)
# -----------------------------------------------------------------------------

def validate_image_size(value):
    """Ensure uploaded images are ≤ 2MB."""
    if value.size > 2 * 1024 * 1024:
        raise ValidationError("Image file too large (max 2MB).")


class PortfolioSettings(models.Model):
    """
    Singleton model for homepage content (hero, about, social links, etc.).
    Only one instance can exist.
    """
    # Hero section
    hero_title = models.CharField(
        max_length=200, blank=True,
        default="Smart ICT Solutions for Modern Businesses"
    )
    hero_subtitle = models.TextField(
        blank=True,
        default=(
            "From managed IT support to custom software, "
            "we deliver technology that drives growth."
        )
    )
    hero_image = models.ImageField(
        upload_to="hero/", null=True, blank=True,
        validators=[validate_image_size]
    )

    # About section
    about_title = models.CharField(
        max_length=200, blank=True,
        default="Your Trusted Technology Partner"
    )
    about_text = models.TextField(
        blank=True,
        default=(
            "We are a team of passionate engineers, developers, and support "
            "specialists dedicated to solving business problems with technology."
        )
    )
    about_image = models.ImageField(
        upload_to="about/", null=True, blank=True,
        validators=[validate_image_size]
    )

    # Achievements counters
    projects_count = models.PositiveIntegerField(default=150)
    satisfaction_percent = models.PositiveIntegerField(default=98)
    support_hours = models.PositiveIntegerField(default=24)
    years_experience = models.PositiveIntegerField(default=12)

    # Social links
    facebook_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    whatsapp_number = models.CharField(
        max_length=20, blank=True, default="265888888888",
        help_text="International format without '+' or with '+', e.g., 265888888888 or +265888888888"
    )

    # SEO
    meta_description = models.CharField(max_length=300, blank=True)
    meta_keywords = models.CharField(max_length=200, blank=True)

    # Footer
    footer_copyright = models.CharField(
        max_length=200, blank=True,
        default="All Right Reserved."
    )

    history = HistoricalRecords()  # Audit log

    class Meta:
        verbose_name = "Portfolio Settings"
        verbose_name_plural = "Portfolio Settings"

    def __str__(self):
        return "Portfolio Settings"

    @classmethod
    def get(cls):
        """Get or create the singleton instance."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        """Enforce singleton: prevent creating a second instance."""
        if not self.pk and PortfolioSettings.objects.exists():
            raise ValidationError("Only one PortfolioSettings instance allowed.")
        super().save(*args, **kwargs)