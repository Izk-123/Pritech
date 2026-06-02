# tickets/models.py
"""
Tickets App Models
------------------
Support tickets, comments, work logs, attachments, SLA, and canned responses.
All Quill fields automatically convert plain text to the required JSON format
(`{"html": "...", "delta": ""}`) on save.
"""

import json
from decimal import Decimal

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from django_quill.fields import QuillField
from simple_history.models import HistoricalRecords


# -----------------------------------------------------------------------------
# Helper function to convert plain text to Quill JSON
# -----------------------------------------------------------------------------
def ensure_quill_json(value):
    """Convert a plain text string to Quill JSON if it is not already JSON."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip().startswith('{'):
        return json.dumps({"html": f"<p>{value}</p>", "delta": ""})
    return value


# -----------------------------------------------------------------------------
# Ticket Model
# -----------------------------------------------------------------------------
class Ticket(models.Model):
    """
    Support ticket with full lifecycle tracking.
    Includes SLA, comments, work logs, and attachments.
    """
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('escalated', 'Escalated'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    VALID_TRANSITIONS = {
        'open': ['assigned', 'closed'],
        'assigned': ['in_progress', 'open'],
        'in_progress': ['resolved', 'escalated', 'assigned'],
        'resolved': ['closed', 'open'],
        'escalated': ['in_progress', 'assigned'],
        'closed': ['open'],
    }

    # Core fields
    ticket_number = models.CharField(max_length=20, unique=True, blank=True)
    title = models.CharField(max_length=300)
    description = QuillField()
    client = models.ForeignKey(
        'clients.ClientOrganization',
        on_delete=models.CASCADE,
        related_name='tickets',
        db_index=True
    )
    service = models.ForeignKey('services.Service', on_delete=models.SET_NULL, null=True, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_tickets',
        db_index=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_tickets'
    )

    # Status & priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', db_index=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium', db_index=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    # Audit log
    history = HistoricalRecords()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.ticket_number} – {self.title}"

    def save(self, *args, **kwargs):
        # Auto-convert plain text description to Quill JSON
        if self.description:
            self.description = ensure_quill_json(self.description)
        # Generate ticket number if not set
        if not self.ticket_number:
            today = timezone.now().strftime('%Y%m%d')
            prefix = f'TKT-{today}-'
            last_today = Ticket.objects.filter(
                ticket_number__startswith=prefix
            ).order_by('-ticket_number').first()
            if last_today:
                last_seq = int(last_today.ticket_number.split('-')[-1])
                seq = f'{last_seq + 1:04d}'
            else:
                seq = '0001'
            self.ticket_number = f'{prefix}{seq}'
        super().save(*args, **kwargs)

    def can_transition_to(self, new_status):
        return new_status in self.VALID_TRANSITIONS.get(self.status, [])

    @property
    def status_color(self):
        """Returns Bootstrap color class for status badge."""
        return {
            'open': 'primary', 'assigned': 'info', 'in_progress': 'warning',
            'resolved': 'success', 'closed': 'secondary', 'escalated': 'danger'
        }.get(self.status, 'secondary')

    @property
    def priority_color(self):
        """Returns Bootstrap color class for priority badge."""
        return {
            'low': 'secondary', 'medium': 'primary', 'high': 'warning', 'critical': 'danger'
        }.get(self.priority, 'secondary')


# -----------------------------------------------------------------------------
# TicketComment
# -----------------------------------------------------------------------------
class TicketComment(models.Model):
    """Comment on a ticket – can be public or internal, and optionally marked as solution."""
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    content = QuillField()
    is_internal = models.BooleanField(default=False)
    is_solution = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def save(self, *args, **kwargs):
        # Auto-convert plain text content to Quill JSON
        self.content = ensure_quill_json(self.content)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Comment on {self.ticket.ticket_number} by {self.author}"


# -----------------------------------------------------------------------------
# TicketWorkLog
# -----------------------------------------------------------------------------
class TicketWorkLog(models.Model):
    """Hours logged by a technician on a ticket."""
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='worklogs')
    technician = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    hours = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.5'))]
    )
    description = QuillField()
    logged_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Auto-convert plain text description to Quill JSON
        self.description = ensure_quill_json(self.description)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.technician} – {self.hours}h on {self.ticket.ticket_number}"


# -----------------------------------------------------------------------------
# TicketAttachment
# -----------------------------------------------------------------------------
class TicketAttachment(models.Model):
    """File attachment uploaded to a ticket."""
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='tickets/%Y/%m/')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Attachment for {self.ticket.ticket_number}"


# -----------------------------------------------------------------------------
# TicketSLA
# -----------------------------------------------------------------------------
class TicketSLA(models.Model):
    """SLA deadlines for response and resolution."""
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name='sla')
    response_due = models.DateTimeField(null=True, blank=True)
    resolution_due = models.DateTimeField(null=True, blank=True)
    breached = models.BooleanField(default=False)

    def __str__(self):
        return f"SLA for {self.ticket.ticket_number}"


# -----------------------------------------------------------------------------
# CannedResponse
# -----------------------------------------------------------------------------
class CannedResponse(models.Model):
    """Predefined reply templates for technicians."""
    title = models.CharField(max_length=100)
    content = models.TextField(help_text="The reply text (supports basic HTML).")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
