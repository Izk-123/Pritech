# services/signals.py
"""
Signals for the Services app:
- Invalidate client catalog cache when a service or package changes.
- Automatically create a ClientService record when an invoice for a service is paid.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.db.models import Q

from .models import Service, ServicePackage
from finance.models import Invoice, InvoiceItem


# -----------------------------------------------------------------------------
# Cache invalidation
# -----------------------------------------------------------------------------
@receiver([post_save, post_delete], sender=Service)
@receiver([post_save, post_delete], sender=ServicePackage)
def clear_service_catalog_cache(sender, **kwargs):
    """Clear the cached service lists when any service or package changes."""
    cache.delete('client_service_catalog_service_ids')
    cache.delete('client_service_catalog_packages')


# -----------------------------------------------------------------------------
# Create ClientService record when an invoice for a service is paid
# -----------------------------------------------------------------------------
@receiver(post_save, sender=Invoice)
def create_client_service_on_paid_invoice(sender, instance, **kwargs):
    """
    When an invoice is marked as 'paid', check if it contains line items
    that correspond to actual services. For each such service, create or update
    a ClientService record.
    """
    if instance.status != 'paid':
        return

    # Get all invoice items whose description matches a service name
    service_names = instance.items.values_list('description', flat=True)
    services = Service.objects.filter(name__in=service_names)

    for service in services:
        # Determine start date (invoice issue date)
        start_date = instance.issue_date
        # For recurring services, we might set end_date later; for one‑off, no end_date
        ClientService.objects.get_or_create(
            client=instance.client,
            service=service,
            defaults={
                'start_date': start_date,
                'status': 'active',
                'invoice': instance
            }
        )