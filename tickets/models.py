from django.db import models
from django.conf import settings
from django.utils import timezone


class Ticket(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'), ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'), ('resolved', 'Resolved'),
        ('closed', 'Closed'), ('escalated', 'Escalated'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'), ('medium', 'Medium'),
        ('high', 'High'), ('critical', 'Critical'),
    ]
    VALID_TRANSITIONS = {
        'open': ['assigned', 'closed'],
        'assigned': ['in_progress', 'open'],
        'in_progress': ['resolved', 'escalated', 'assigned'],
        'resolved': ['closed', 'open'],
        'escalated': ['in_progress', 'assigned'],
        'closed': ['open'],
    }

    ticket_number = models.CharField(max_length=20, unique=True, blank=True)  # NEW
    title = models.CharField(max_length=300)
    description = models.TextField()
    client = models.ForeignKey('clients.ClientOrganization', on_delete=models.CASCADE, related_name='tickets')
    service = models.ForeignKey('services.Service', on_delete=models.SET_NULL, null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='assigned_tickets')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='created_tickets')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.ticket_number} – {self.title}"

    def save(self, *args, **kwargs):
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
        return {
            'open': 'blue', 'assigned': 'purple', 'in_progress': 'amber',
            'resolved': 'teal', 'closed': 'gray', 'escalated': 'red'
        }.get(self.status, 'gray')

    @property
    def priority_color(self):
        return {'low': 'gray', 'medium': 'blue', 'high': 'amber', 'critical': 'red'}.get(self.priority, 'gray')


class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class TicketWorkLog(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='worklogs')
    technician = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    description = models.TextField()
    logged_at = models.DateTimeField(auto_now_add=True)


# ─── NEW MODELS ───────────────────────────────────────────────────────────────

class TicketAttachment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='tickets/%Y/%m/')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Attachment for {self.ticket.ticket_number}"


class TicketSLA(models.Model):
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name='sla')
    response_due = models.DateTimeField(null=True, blank=True)
    resolution_due = models.DateTimeField(null=True, blank=True)
    breached = models.BooleanField(default=False)

    def __str__(self):
        return f"SLA for {self.ticket.ticket_number}"