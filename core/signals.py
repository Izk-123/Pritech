# core/signals.py
"""
Clear dashboard cache and create activity feed entries.
"""

from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from tickets.models import Ticket
from finance.models import Invoice, Quotation, Payment
from clients.models import ClientOrganization
from accounts.models import User
from .models import ActivityFeed


def create_activity(module, action, user=None, object_id=''):
    """Helper to create an activity feed entry."""
    ActivityFeed.objects.create(module=module, action=action, user=user, object_id=object_id)


@receiver([post_save, post_delete], sender=Ticket)
@receiver([post_save, post_delete], sender=Invoice)
@receiver([post_save, post_delete], sender=ClientOrganization)
def invalidate_dashboard_cache(sender, **kwargs):
    """Clear dashboard aggregate caches when relevant data changes."""
    cache.delete('dashboard_finance_aggregates')
    cache.delete('dashboard_admin_aggregates')


@receiver(post_save, sender=Ticket)
def ticket_activity(sender, instance, created, **kwargs):
    if created:
        create_activity('tickets', f"Ticket #{instance.ticket_number} created", instance.created_by, str(instance.pk))


@receiver(post_save, sender=Invoice)
def invoice_activity(sender, instance, created, **kwargs):
    if created:
        create_activity('finance', f"Invoice {instance.invoice_number} created", instance.created_by, str(instance.pk))


@receiver(post_save, sender=Quotation)
def quotation_activity(sender, instance, created, **kwargs):
    if created:
        create_activity('finance', f"Quotation {instance.quotation_number} created", instance.created_by, str(instance.pk))


@receiver(post_save, sender=Payment)
def payment_activity(sender, instance, created, **kwargs):
    if created:
        create_activity('finance', f"Payment of {instance.amount} received for invoice {instance.invoice.invoice_number}", None, str(instance.pk))


@receiver(post_save, sender=ClientOrganization)
def client_activity(sender, instance, created, **kwargs):
    if created:
        create_activity('clients', f"Client {instance.name} registered", None, str(instance.pk))