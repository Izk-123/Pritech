# services/models.py
"""
Services App Models
-------------------
Service categories, services, and packages.
Includes:
- Slug field for SEO‑friendly URLs (auto‑generated from name)
- Database indexes on foreign keys
- Simple history for audit logging
- Plain text to Quill JSON conversion (via save method)
"""

import json
from django.db import models
from django.utils.text import slugify
from django_quill.fields import QuillField
from simple_history.models import HistoricalRecords


def ensure_quill_json(value):
    """Convert plain text to Quill JSON if needed."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip().startswith('{'):
        return json.dumps({"html": f"<p>{value}</p>", "delta": ""})
    return value


class ServiceCategory(models.Model):
    """Category for organising services."""
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, default='🔧')
    description = QuillField(blank=True)
    history = HistoricalRecords()   # audit log

    class Meta:
        verbose_name_plural = 'Service categories'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.description:
            self.description = ensure_quill_json(self.description)
        super().save(*args, **kwargs)


class Service(models.Model):
    """Individual service offered to clients."""
    BILLING_TYPE_CHOICES = [
        ('one_time', 'One Time'),
        ('recurring', 'Recurring'),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)  # SEO‑friendly URL
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='services',
        db_index=True      # performance index
    )
    description = QuillField(blank=True)
    base_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit = models.CharField(max_length=50, default='job',
                            help_text='e.g. job, hour, month')
    billing_type = models.CharField(max_length=20, choices=BILLING_TYPE_CHOICES, default='one_time')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()   # audit log

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Auto‑generate slug from name if missing
        if not self.slug:
            self.slug = slugify(self.name)
        # Convert plain text description to Quill JSON
        if self.description:
            self.description = ensure_quill_json(self.description)
        super().save(*args, **kwargs)


class ServicePackage(models.Model):
    """Bundle of multiple services at a fixed monthly price."""
    name = models.CharField(max_length=200)
    description = QuillField(blank=True)
    services = models.ManyToManyField(Service, related_name='packages')
    monthly_price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()   # audit log

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.description:
            self.description = ensure_quill_json(self.description)
        super().save(*args, **kwargs)