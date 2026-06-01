# tickets/tasks.py
from celery import shared_task
from django.utils import timezone
from .models import TicketSLA
from infrastructure.notifications import send_sla_breach_notification

@shared_task
def check_sla_breaches():
    """Periodic task to mark breached SLAs and send alerts."""
    now = timezone.now()
    # Find SLAs that are overdue but not yet marked breached
    slas = TicketSLA.objects.filter(
        breached=False,
        resolution_due__lt=now
    ).select_related('ticket', 'ticket__assigned_to', 'ticket__client')

    for sla in slas:
        sla.breached = True
        sla.save(update_fields=['breached'])
        send_sla_breach_notification(sla.ticket)