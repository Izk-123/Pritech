"""
Portfolio App Models
====================
Complete portfolio showcase with categories, technologies, galleries, testimonials,
and integration with Services app.
All models support audit logging (simple_history) and proper indexes.
"""

import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from django_quill.fields import QuillField
from simple_history.models import HistoricalRecords
import bleach


# -----------------------------------------------------------------------------
# Custom QuillField that sanitizes HTML (XSS prevention)
# -----------------------------------------------------------------------------
class SanitizingQuillField(QuillField):
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
# Portfolio Category
# -----------------------------------------------------------------------------
class PortfolioCategory(models.Model):
    """Organise projects by type (e.g., Web Development, Networking)."""
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome icon class, e.g., 'fa-solid fa-globe'")
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    history = HistoricalRecords()

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "Portfolio Categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            original_slug = self.slug
            counter = 1
            while PortfolioCategory.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


# -----------------------------------------------------------------------------
# Portfolio Technology
# -----------------------------------------------------------------------------
class PortfolioTechnology(models.Model):
    """Technologies used in projects (e.g., Django, Cisco)."""
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome or custom class")
    website = models.URLField(blank=True, help_text="Official technology website")
    is_active = models.BooleanField(default=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Portfolio Technologies"

    def __str__(self):
        return self.name


# -----------------------------------------------------------------------------
# Portfolio Project (main model)
# -----------------------------------------------------------------------------
class PortfolioProject(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    # Basic info
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    category = models.ForeignKey(
        PortfolioCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects"
    )
    client_name = models.CharField(max_length=200, blank=True)
    description = SanitizingQuillField(blank=True)
    full_description = SanitizingQuillField(blank=True, help_text="Detailed project description (optional)")

    # Media
    featured_image = models.ImageField(upload_to="portfolio/", null=True, blank=True)
    project_url = models.URLField(blank=True, help_text="Live project URL (if applicable)")

    # Dates
    start_date = models.DateField(null=True, blank=True)
    completion_date = models.DateField(null=True, blank=True)

    # Status & visibility
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="published")
    is_featured = models.BooleanField(default=False, help_text="Show on homepage")
    order = models.IntegerField(default=0, help_text="Order for featured projects")

    # Relationships
    services = models.ManyToManyField(
        "services.Service",
        related_name="portfolio_projects",
        blank=True,
        help_text="Select the services that were used in this project."
    )
    technologies = models.ManyToManyField(
        PortfolioTechnology,
        related_name="projects",
        blank=True
    )

    # Meta
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["-is_featured", "order", "-completion_date", "-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["status", "is_featured"]),
            models.Index(fields=["completion_date"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            original_slug = self.slug
            counter = 1
            while PortfolioProject.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse("project_detail", kwargs={"slug": self.slug})


# -----------------------------------------------------------------------------
# Portfolio Image (gallery)
# -----------------------------------------------------------------------------
class PortfolioImage(models.Model):
    project = models.ForeignKey(PortfolioProject, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="portfolio/gallery/")
    caption = models.CharField(max_length=200, blank=True)
    order = models.IntegerField(default=0)
    history = HistoricalRecords()

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self):
        return f"Image for {self.project.title}"


# -----------------------------------------------------------------------------
# Testimonial (client feedback)
# -----------------------------------------------------------------------------
class Testimonial(models.Model):
    project = models.ForeignKey(
        PortfolioProject,
        on_delete=models.CASCADE,
        related_name="testimonials",
        null=True,
        blank=True
    )
    client_name = models.CharField(max_length=150)
    client_position = models.CharField(max_length=150, blank=True)
    testimonial = models.TextField()
    rating = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1–5 stars"
    )
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Testimonial from {self.client_name}"


# -----------------------------------------------------------------------------
# Inquiry (contact form submission)
# -----------------------------------------------------------------------------
class Inquiry(models.Model):
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
    history = HistoricalRecords()

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
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    is_confirmed = models.BooleanField(default=False)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    confirmation_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    consent_given = models.BooleanField(default=False)
    consent_ip = models.GenericIPAddressField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    history = HistoricalRecords()

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
        return self.is_confirmed and self.unsubscribed_at is None


# -----------------------------------------------------------------------------
# Portfolio Settings (singleton)
# -----------------------------------------------------------------------------
def validate_image_size(value):
    if value.size > 2 * 1024 * 1024:
        raise ValidationError("Image file too large (max 2MB).")


class PortfolioSettings(models.Model):
    hero_title = models.CharField(max_length=200, blank=True, default="Smart ICT Solutions for Modern Businesses")
    hero_subtitle = models.TextField(blank=True, default="From managed IT support to custom software...")
    hero_image = models.ImageField(upload_to="hero/", null=True, blank=True, validators=[validate_image_size])
    about_title = models.CharField(max_length=200, blank=True, default="Your Trusted Technology Partner")
    about_text = models.TextField(blank=True)
    about_image = models.ImageField(upload_to="about/", null=True, blank=True, validators=[validate_image_size])
    projects_count = models.PositiveIntegerField(default=150)
    satisfaction_percent = models.PositiveIntegerField(default=98)
    support_hours = models.PositiveIntegerField(default=24)
    years_experience = models.PositiveIntegerField(default=12)
    facebook_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True, default="265888888888")
    meta_description = models.CharField(max_length=300, blank=True)
    meta_keywords = models.CharField(max_length=200, blank=True)
    footer_copyright = models.CharField(max_length=200, blank=True, default="All Right Reserved.")
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Portfolio Settings"
        verbose_name_plural = "Portfolio Settings"

    def __str__(self):
        return "Portfolio Settings"

    @classmethod
    def get(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        if not self.pk and PortfolioSettings.objects.exists():
            raise ValidationError("Only one PortfolioSettings instance allowed.")
        super().save(*args, **kwargs)