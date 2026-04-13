from django.db import models
from django.conf import settings
import uuid


class ClientOrganization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    INDUSTRY_CHOICES = [
        ('technology', 'Technology'), ('finance', 'Finance & Banking'),
        ('healthcare', 'Healthcare'), ('education', 'Education'),
        ('government', 'Government'), ('ngo', 'NGO / Non-Profit'),
        ('retail', 'Retail & Commerce'), ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('lead', 'Lead'),
        ('former', 'Former Client'),
    ]

    name = models.CharField(max_length=200)
    industry = models.CharField(max_length=50, choices=INDUSTRY_CHOICES, default='other')
    registration_number = models.CharField(max_length=100, blank=True)
    tax_id = models.CharField(max_length=100, blank=True)  # new field
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')  # replace is_active
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Link to the primary user (one user = one organization for MVP)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='client_organization'
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def open_tickets(self):
        return self.tickets.exclude(status='closed').count()

    @property
    def total_invoiced(self):
        from django.db.models import Sum
        return self.invoices.aggregate(t=Sum('total_amount'))['t'] or 0


class ClientContact(models.Model):
    client = models.ForeignKey(ClientOrganization, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.client})"
