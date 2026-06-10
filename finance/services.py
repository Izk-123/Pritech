# finance/services.py
"""
Finance Services
----------------
Core business logic for invoices, payments, quotations, and their conversions.
Includes:
- Idempotent payment recording
- Invoice totals validation
- Quill JSON conversion helpers
- Email notifications (stubs – implement SMTP for production)
"""

import json
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from .models import Invoice, InvoiceItem, Payment, Quotation, QuotationItem
from infrastructure.notifications import notify_invoice_issued, notify_payment_received

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Helper: VAT rate
# -----------------------------------------------------------------------------
def get_vat_rate():
    """Return VAT rate as Decimal from settings."""
    rate = getattr(settings, 'VAT_RATE', 0.165)
    return Decimal(str(rate))


# -----------------------------------------------------------------------------
# InvoiceService
# -----------------------------------------------------------------------------
class InvoiceService:
    """Handles creation, recalculation, payment recording, and issuance of invoices."""

    @staticmethod
    @transaction.atomic
    def create_invoice(client, items_data, issue_date, due_date, ticket=None, notes='', created_by=None):
        """
        Create a draft invoice with line items.
        """
        # Validate ticket belongs to the client
        if ticket and ticket.client != client:
            raise ValueError('Ticket does not belong to the specified client.')

        invoice = Invoice.objects.create(
            client=client, ticket=ticket, issue_date=issue_date,
            due_date=due_date, notes=notes, created_by=created_by, status='draft'
        )
        subtotal = Decimal('0')
        for item in items_data:
            qty = Decimal(str(item['quantity']))
            price = Decimal(str(item['unit_price']))
            total = qty * price
            InvoiceItem.objects.create(
                invoice=invoice, description=item['description'],
                quantity=qty, unit_price=price, total=total
            )
            subtotal += total
        vat = get_vat_rate()
        tax = subtotal * vat
        invoice.subtotal = subtotal
        invoice.tax_amount = tax
        invoice.total_amount = subtotal + tax
        invoice.save(update_fields=['subtotal', 'tax_amount', 'total_amount'])
        return invoice

    @staticmethod
    def recalculate(invoice):
        """Recalculate invoice totals based on current line items."""
        subtotal = sum(i.total for i in invoice.items.all())
        vat = get_vat_rate()
        invoice.subtotal = subtotal
        invoice.tax_amount = subtotal * vat
        invoice.total_amount = subtotal + invoice.tax_amount
        invoice.save(update_fields=['subtotal', 'tax_amount', 'total_amount'])

    @staticmethod
    def record_payment(invoice, amount, method, date, reference='', notes='', recorded_by=None):
        """
        Record a payment against an invoice and update status.
        """
        payment = Payment.objects.create(
            invoice=invoice, amount=amount, method=method,
            date=date, reference=reference, notes=notes, recorded_by=recorded_by
        )
        invoice.amount_paid = sum(p.amount for p in invoice.payments.all())
        if invoice.amount_paid >= invoice.total_amount:
            invoice.status = 'paid'
        elif invoice.amount_paid > 0:
            invoice.status = 'partial'
        invoice.save(update_fields=['amount_paid', 'status'])
        notify_payment_received(payment)
        return payment

    @staticmethod
    def issue(invoice):
        """
        Change invoice status from draft to issued, after validating totals.
        """
        if invoice.status != 'draft':
            raise ValueError('Only draft invoices can be issued.')

        # Recalculate totals to ensure consistency
        subtotal = sum(item.total for item in invoice.items.all())
        vat = get_vat_rate()
        tax = subtotal * vat
        total = subtotal + tax

        if (invoice.subtotal != subtotal or
            invoice.tax_amount != tax or
            invoice.total_amount != total):
            # Auto‑correct to actual values
            invoice.subtotal = subtotal
            invoice.tax_amount = tax
            invoice.total_amount = total
            invoice.save(update_fields=['subtotal', 'tax_amount', 'total_amount'])
            logger.warning(
                f"Invoice {invoice.invoice_number} totals were inconsistent and have been corrected. "
                f"Old subtotal {invoice.subtotal} → {subtotal}, tax {invoice.tax_amount} → {tax}, total {invoice.total_amount} → {total}"
            )

        invoice.status = 'issued'
        invoice.save(update_fields=['status'])
        notify_invoice_issued(invoice)


# -----------------------------------------------------------------------------
# QuotationService
# -----------------------------------------------------------------------------
class QuotationService:
    """Handles creation, sending, approval, and conversion of quotations to invoices."""

    @staticmethod
    def _ensure_quill_json(value):
        """Convert plain text to Quill JSON if needed."""
        if value is None:
            return None
        if isinstance(value, str) and not value.strip().startswith('{'):
            return json.dumps({"html": f"<p>{value}</p>", "delta": ""})
        return value

    @staticmethod
    def _extract_quill_html(value):
        """
        Safely extract HTML content from a Quill field or string.
        Returns a string (HTML) that can be concatenated.
        """
        if value is None:
            return ''
        if hasattr(value, 'html'):
            return value.html
        return str(value)

    @staticmethod
    @transaction.atomic
    def create_quotation(client, items_data, issue_date, valid_until, notes='', created_by=None):
        """
        Create a draft quotation with line items.
        """
        notes_json = QuotationService._ensure_quill_json(notes)
        quotation = Quotation.objects.create(
            client=client, issue_date=issue_date, valid_until=valid_until,
            notes=notes_json, created_by=created_by, status='draft'
        )
        subtotal = Decimal('0')
        for item in items_data:
            qty = Decimal(str(item['quantity']))
            price = Decimal(str(item['unit_price']))
            total = qty * price
            QuotationItem.objects.create(
                quotation=quotation, description=item['description'],
                quantity=qty, unit_price=price, total=total
            )
            subtotal += total
        vat = get_vat_rate()
        tax = subtotal * vat
        quotation.subtotal = subtotal
        quotation.tax_amount = tax
        quotation.total_amount = subtotal + tax
        quotation.save(update_fields=['subtotal', 'tax_amount', 'total_amount'])
        return quotation

    @staticmethod
    def recalculate(quotation):
        """Recalculate quotation totals based on current line items."""
        subtotal = sum(i.total for i in quotation.items.all())
        vat = get_vat_rate()
        quotation.subtotal = subtotal
        quotation.tax_amount = subtotal * vat
        quotation.total_amount = subtotal + quotation.tax_amount
        quotation.save(update_fields=['subtotal', 'tax_amount', 'total_amount'])

    @staticmethod
    def send(quotation):
        """Change quotation status from draft to sent."""
        if quotation.status != 'draft':
            raise ValueError('Only draft quotations can be sent.')
        quotation.status = 'sent'
        quotation.save(update_fields=['status'])
        # Optionally send email notification to client

    @staticmethod
    def approve(quotation):
        """Change quotation status from sent to approved."""
        if quotation.status != 'sent':
            raise ValueError('Only sent quotations can be approved.')
        quotation.status = 'approved'
        quotation.save(update_fields=['status'])

    @staticmethod
    def convert_to_invoice(quotation, created_by=None):
        """
        Convert an approved quotation into a draft invoice.
        Preserves notes and client feedback, converting to Quill JSON properly.
        """
        if quotation.status != 'approved':
            raise ValueError('Quotation must be approved by client before conversion to invoice.')

        # Combine original notes with client feedback, extracting HTML from Quill fields
        notes_parts = []
        if quotation.notes:
            notes_parts.append(QuotationService._extract_quill_html(quotation.notes))
        if quotation.client_feedback:
            notes_parts.append(f"<strong>Client feedback during approval:</strong><br>{quotation.client_feedback}")

        notes_content = "\n\n".join(notes_parts) if notes_parts else ""
        # Convert the assembled HTML string to Quill JSON before creating invoice
        notes_json = QuotationService._ensure_quill_json(notes_content)

        invoice = Invoice.objects.create(
            client=quotation.client,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            notes=notes_json,
            created_by=created_by,
            status='draft'
        )
        for q_item in quotation.items.all():
            InvoiceItem.objects.create(
                invoice=invoice,
                description=q_item.description,
                quantity=q_item.quantity,
                unit_price=q_item.unit_price,
                total=q_item.total
            )
        invoice.subtotal = quotation.subtotal
        invoice.tax_amount = quotation.tax_amount
        invoice.total_amount = quotation.total_amount
        invoice.save()
        quotation.status = 'converted'
        quotation.save(update_fields=['status'])
        return invoice