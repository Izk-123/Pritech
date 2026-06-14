# clients/models.py
"""
Clients App Models
------------------
ClientOrganization (companies) and ClientContact (individuals).
Includes:
- Audit logging via simple_history
- Database indexes on frequently filtered fields
- Unique constraints on email/phone
- Logo field for branding
- Assigned sales representative
- QuillField for rich text notes (sanitized in templates)
"""

import uuid
from django.db import models
from django.conf import settings
from django_quill.fields import QuillField
from simple_history.models import HistoricalRecords


class ClientOrganization(models.Model):
    """Client company/organization."""
    # Primary key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Industry choices
    INDUSTRY_CHOICES = [
        ('technology', 'Technology'),
        ('finance', 'Finance & Banking'),
        ('healthcare', 'Healthcare'),
        ('education', 'Education'),
        ('government', 'Government'),
        ('ngo', 'NGO / Non-Profit'),
        ('retail', 'Retail & Commerce'),
        ('other', 'Other'),
    ]

    # Status choices
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('lead', 'Lead'),
        ('former', 'Former Client'),
    ]

    # Core fields
    name = models.CharField(max_length=200, db_index=True)
    industry = models.CharField(max_length=50, choices=INDUSTRY_CHOICES, default='other', db_index=True)
    registration_number = models.CharField(max_length=100, blank=True)
    tax_id = models.CharField(max_length=100, blank=True)

    # Contact details (unique to prevent duplicates)
    email = models.EmailField(blank=True, unique=True, db_index=True)
    phone = models.CharField(max_length=20, blank=True, unique=True, db_index=True)

    address = models.TextField(blank=True)
    website = models.URLField(blank=True)

    # Rich text notes (Quill) – will be sanitized in template
    notes = QuillField(blank=True)

    # Status and timestamps
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # Branding (low‑risk improvement)
    logo = models.ImageField(upload_to='client_logos/', null=True, blank=True)

    # Sales assignment (high‑risk improvement)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_clients',
        db_index=True,
        help_text="Sales representative responsible for this client"
    )

    # Link to the client user account (one‑to‑one)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='primary_organization'
    )

    # Audit log (critical)
    history = HistoricalRecords()

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def open_tickets(self):
        """Number of open tickets (not closed) for this client."""
        return self.tickets.exclude(status='closed').count()

    @property
    def total_invoiced(self):
        """Total invoice amount (all invoices)."""
        from django.db.models import Sum
        return self.invoices.aggregate(t=Sum('total_amount'))['t'] or 0


class ClientContact(models.Model):
    """Individual contact person for a client organisation."""
    client = models.ForeignKey(ClientOrganization, on_delete=models.CASCADE, related_name='contacts', db_index=True)
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_primary = models.BooleanField(default=False)
    history = HistoricalRecords()   # audit log

    def __str__(self):
        return f"{self.name} ({self.client.name})"