# finance/tasks.py
import logging
from decimal import Decimal

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

from .models import ClientSubscription, Invoice, Quotation
from .services import InvoiceService
from core.models import SiteConfig

logger = logging.getLogger(__name__)


@shared_task
def generate_subscription_invoices():
    """Run on the 1st of each month. Creates invoices for active subscriptions."""
    today = timezone.now().date()
    subscriptions = ClientSubscription.objects.filter(
        status='active',
        current_period_start__lte=today,
        current_period_end__gte=today,
    )

    created_count = 0
    for sub in subscriptions:
        if Invoice.objects.filter(
            subscription=sub,
            issue_date__year=today.year,
            issue_date__month=today.month,
        ).exists():
            continue

        items_data = [{
            'description': f"Subscription: {sub.plan.name} - {today.strftime('%B %Y')}",
            'quantity': Decimal('1'),
            'unit_price': sub.plan.monthly_price,
        }]

        invoice = InvoiceService.create_invoice(
            client=sub.client,
            items_data=items_data,
            issue_date=today,
            due_date=today + timezone.timedelta(days=30),
            notes=f"Monthly subscription fee for {sub.plan.name}.",
            created_by=None,
            include_vat=True,
        )
        invoice.subscription = sub
        invoice.save(update_fields=['subscription'])
        created_count += 1

    logger.info(f"Generated {created_count} subscription invoices for {today}")
    return f"Generated {created_count} subscription invoices."


@shared_task(time_limit=60, soft_time_limit=50)
def generate_invoice_pdf(invoice_id):
    """Generate PDF for an invoice using ReportLab and cache it."""
    from infrastructure.pdf_reportlab import render_invoice_pdf, load_logo_data_uri

    try:
        invoice = Invoice.objects.get(pk=invoice_id)
    except Invoice.DoesNotExist:
        logger.error(f"Invoice {invoice_id} not found for PDF generation.")
        return

    config = SiteConfig.get()
    logo_data_uri = load_logo_data_uri()

    try:
        pdf_bytes = render_invoice_pdf(invoice, config, logo_data_uri)
    except Exception as e:
        logger.exception(f"ReportLab failed for invoice {invoice.invoice_number}: {e}")
        return

    cache.set(f'invoice_pdf_{invoice_id}', pdf_bytes, timeout=3600)
    logger.info(f"Generated ReportLab PDF for invoice {invoice.invoice_number}")
    return f"Invoice {invoice.invoice_number} PDF generated."


@shared_task(time_limit=60, soft_time_limit=50)
def generate_quotation_pdf(quotation_id):
    """Generate PDF for a quotation using ReportLab and cache it."""
    from infrastructure.pdf_reportlab import render_quotation_pdf, load_logo_data_uri

    try:
        quotation = Quotation.objects.get(pk=quotation_id)
    except Quotation.DoesNotExist:
        logger.error(f"Quotation {quotation_id} not found for PDF generation.")
        return

    config = SiteConfig.get()
    logo_data_uri = load_logo_data_uri()

    try:
        pdf_bytes = render_quotation_pdf(quotation, config, logo_data_uri)
    except Exception as e:
        logger.exception(f"ReportLab failed for quotation {quotation.quotation_number}: {e}")
        return

    cache.set(f'quotation_pdf_{quotation_id}', pdf_bytes, timeout=3600)
    logger.info(f"Generated ReportLab PDF for quotation {quotation.quotation_number}")
    return f"Quotation {quotation.quotation_number} PDF generated."