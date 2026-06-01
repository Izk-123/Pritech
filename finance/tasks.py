# finance/tasks.py
import base64
import logging
from decimal import Decimal

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings

from .models import ClientSubscription, Invoice, Quotation
from .services import InvoiceService
from core.models import SiteConfig

logger = logging.getLogger(__name__)


@shared_task
def generate_subscription_invoices():
    """
    Run on the 1st of each month (or via periodic schedule).
    Creates an invoice for every active subscription whose current period includes today.
    """
    today = timezone.now().date()
    subscriptions = ClientSubscription.objects.filter(
        status='active',
        current_period_start__lte=today,
        current_period_end__gte=today
    )

    created_count = 0
    for sub in subscriptions:
        # Avoid duplicate invoices for the same month
        if Invoice.objects.filter(
            subscription=sub,
            issue_date__year=today.year,
            issue_date__month=today.month
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
            created_by=None  # system user
        )
        # Link invoice to subscription
        invoice.subscription = sub
        invoice.save(update_fields=['subscription'])
        created_count += 1

    logger.info(f"Generated {created_count} subscription invoices for {today}")
    return f"Generated {created_count} subscription invoices."


@shared_task(time_limit=60, soft_time_limit=50)
def generate_invoice_pdf(invoice_id):
    """
    Generate PDF for an invoice and store in cache.
    Runs asynchronously to avoid blocking the request.
    """
    from infrastructure.pdf_service import render_pdf, pdf_response
    from infrastructure.pdf_sanitizer import sanitize_html, sanitize_plain_text

    try:
        invoice = Invoice.objects.get(pk=invoice_id)
    except Invoice.DoesNotExist:
        logger.error(f"Invoice {invoice_id} not found for PDF generation.")
        return

    config = SiteConfig.get()
    vat_percent = float(config.vat_rate) * 100

    notes_html = sanitize_html(invoice.notes) if invoice.notes else ''
    items = []
    for item in invoice.items.all():
        items.append({
            'description': sanitize_plain_text(item.description),
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'total': item.total,
        })

    logo_path = settings.BASE_DIR / 'static' / 'images' / 'logo.png'
    logo_data_uri = ""
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            logo_bytes = f.read()
            b64 = base64.b64encode(logo_bytes).decode('utf-8')
            logo_data_uri = f"data:image/png;base64,{b64}"
    else:
        logger.warning(f"Logo file not found at {logo_path}. Generating PDF without logo.")

    pdf_bytes = render_pdf('finance/invoice_pdf.html', {
        'invoice': invoice,
        'items': items,
        'config': config,
        'vat_percent': f'{vat_percent:.1f}',
        'static_logo_data_uri': logo_data_uri,
        'notes_html': notes_html,
    })

    cache_key = f'invoice_pdf_{invoice_id}'
    cache.set(cache_key, pdf_bytes, timeout=3600)  # cache for 1 hour
    logger.info(f"Generated PDF for invoice {invoice.invoice_number}")
    return f"Invoice {invoice.invoice_number} PDF generated."


@shared_task(time_limit=60, soft_time_limit=50)
def generate_quotation_pdf(quotation_id):
    """
    Generate PDF for a quotation and store in cache.
    Runs asynchronously.
    """
    from infrastructure.pdf_service import render_pdf
    from infrastructure.pdf_sanitizer import sanitize_html, sanitize_plain_text

    try:
        quotation = Quotation.objects.get(pk=quotation_id)
    except Quotation.DoesNotExist:
        logger.error(f"Quotation {quotation_id} not found for PDF generation.")
        return

    config = SiteConfig.get()
    vat_percent = float(config.vat_rate) * 100

    notes_html = sanitize_html(quotation.notes) if quotation.notes else ''
    feedback_html = sanitize_html(quotation.client_feedback) if quotation.client_feedback else ''
    items = []
    for item in quotation.items.all():
        items.append({
            'description': sanitize_plain_text(item.description),
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'total': item.total,
        })

    logo_path = settings.BASE_DIR / 'static' / 'images' / 'logo.png'
    logo_data_uri = ""
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            logo_bytes = f.read()
            b64 = base64.b64encode(logo_bytes).decode('utf-8')
            logo_data_uri = f"data:image/png;base64,{b64}"
    else:
        logger.warning(f"Logo file not found at {logo_path}. Generating PDF without logo.")

    pdf_bytes = render_pdf('finance/quotation_pdf.html', {
        'quotation': quotation,
        'items': items,
        'config': config,
        'vat_percent': f'{vat_percent:.1f}',
        'static_logo_data_uri': logo_data_uri,
        'notes_html': notes_html,
        'feedback_html': feedback_html,
    })

    cache_key = f'quotation_pdf_{quotation_id}'
    cache.set(cache_key, pdf_bytes, timeout=3600)
    logger.info(f"Generated PDF for quotation {quotation.quotation_number}")
    return f"Quotation {quotation.quotation_number} PDF generated."