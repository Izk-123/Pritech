# services/models.py
"""
Services App Models
-------------------
Core models: ServiceCategory, Service, ServicePackage.
Extended models for full lifecycle management:
- ServiceRequest: client demand with approval workflow
- ClientService: purchased services (active/historical)
- ServiceAssignment: technician assignment to service requests

All Quill fields are handled by django-quill – no custom JSON conversion.
Slugs are auto‑generated with uniqueness handling.
"""

import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django_quill.fields import QuillField
from simple_history.models import HistoricalRecords


# -----------------------------------------------------------------------------
# Service Category (simple classification)
# -----------------------------------------------------------------------------
class ServiceCategory(models.Model):
    """Category for organising services (e.g., Networking, Hardware)."""
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, default='🔧')
    description = QuillField(blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name_plural = 'Service categories'

    def __str__(self):
        return self.name


# -----------------------------------------------------------------------------
# Individual Service
# -----------------------------------------------------------------------------
class Service(models.Model):
    """Individual service offered to clients."""
    BILLING_TYPE_CHOICES = [
        ('one_time', 'One Time'),
        ('recurring', 'Recurring'),
    ]

    name = models.CharField(max_length=200, unique=True)          # unique constraint
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='services',
        db_index=True
    )
    description = QuillField(blank=True)
    base_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit = models.CharField(max_length=50, default='job',
                            help_text='e.g. job, hour, month')
    billing_type = models.CharField(max_length=20, choices=BILLING_TYPE_CHOICES, default='one_time')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['name'], name='unique_service_name')
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Auto‑generate unique slug from name
        if not self.slug:
            base_slug = slugify(self.name)
            self.slug = base_slug
            counter = 1
            while Service.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


# -----------------------------------------------------------------------------
# Service Package (bundle of services)
# -----------------------------------------------------------------------------
class ServicePackage(models.Model):
    """Bundle of multiple services at a fixed monthly price."""
    name = models.CharField(max_length=200)
    description = QuillField(blank=True)
    services = models.ManyToManyField(Service, related_name='packages')
    monthly_price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# =============================================================================
# EXTENDED MODELS (full lifecycle management)
# =============================================================================

class ServiceRequest(models.Model):
    """
    Client‑initiated request for a specific service.
    Tracks the entire workflow from request to completion.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('quoted', 'Quotation Sent'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    client = models.ForeignKey(
        'clients.ClientOrganization',
        on_delete=models.CASCADE,
        related_name='service_requests',
        db_index=True
    )
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='requests')
    description = models.TextField(blank=True, help_text="Client's additional details")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_requests'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    # Link to the final quotation (if any)
    quotation = models.ForeignKey(
        'finance.Quotation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='service_request'
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"{self.client.name} - {self.service.name} ({self.status})"


class ClientService(models.Model):
    """
    Service that a client has purchased (active subscription or one‑off).
    Created automatically when an invoice for a service is paid.
    """
    client = models.ForeignKey(
        'clients.ClientOrganization',
        on_delete=models.CASCADE,
        related_name='client_services'
    )
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='client_services')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('expired', 'Expired'), ('cancelled', 'Cancelled')],
        default='active'
    )
    # Optional link to the invoice that created this record
    invoice = models.ForeignKey('finance.Invoice', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.client.name} - {self.service.name} ({self.status})"


class ServiceAssignment(models.Model):
    """
    Assignment of a technician to a specific service request.
    Tracks progress and completion.
    """
    service_request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='assignments')
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='service_assignments'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['-assigned_at']

    def __str__(self):
        return f"{self.service_request} → {self.technician.email}"