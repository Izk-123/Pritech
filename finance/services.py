# finance/services.py
"""
Finance Services
================
Core business logic for invoices, payments, quotations, receipts, and their
conversions.

Responsibilities
----------------
- Invoice creation, recalculation, issuance, and payment recording.
- Automatic receipt issuance when an invoice becomes fully paid.
- Quotation creation, workflow (send → approve), and conversion to invoice.
- Quill (rich text) JSON conversion helpers.
- Email notifications (invoice issued, payment received).

Rules
-----
- A payment that fully settles an invoice (amount_paid >= total_amount)
  triggers the automatic creation of a Receipt.
- Partial payments do NOT create a receipt.
- Receipt creation is idempotent: calling it twice on the same payment
  returns the existing receipt instead of erroring.
- All state changes that touch multiple rows run inside a DB transaction.
"""

import json
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from .models import (
    Invoice, InvoiceItem,
    Payment,
    Quotation, QuotationItem,
    Receipt,
)
from infrastructure.notifications import (
    notify_invoice_issued,
    notify_payment_received,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Helpers
# =============================================================================
def get_vat_rate():
    """
    Return the configured VAT rate as a Decimal (default 17.5%).

    Read from `settings.VAT_RATE` so it can be overridden per environment.
    """
    rate = getattr(settings, 'VAT_RATE', 0.175)
    return Decimal(str(rate))


# =============================================================================
# INVOICE SERVICE
# =============================================================================
class InvoiceService:
    """
    Handles invoice lifecycle:
      create → recalculate → issue → record payments (auto-receipt on full pay).
    """

    # -------------------------------------------------------------------------
    # Creation
    # -------------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def create_invoice(
        client, items_data, issue_date, due_date,
        ticket=None, notes='', created_by=None, include_vat=True,
    ):
        """
        Create a draft invoice with line items.

        Args:
            client:       ClientOrganization instance.
            items_data:   List of dicts: {description, quantity, unit_price}.
            issue_date:   date — invoice issue date.
            due_date:     date — payment due date.
            ticket:       Optional Ticket the invoice is linked to.
            notes:        Free-text notes (converted to Quill JSON on save).
            created_by:   User instance or None.
            include_vat:  bool — apply VAT or not.

        Returns:
            The saved Invoice instance.

        Raises:
            ValueError: if `ticket` belongs to a different client.
        """
        if ticket and ticket.client != client:
            raise ValueError('Ticket does not belong to the specified client.')

        invoice = Invoice.objects.create(
            client=client,
            ticket=ticket,
            issue_date=issue_date,
            due_date=due_date,
            notes=notes,
            created_by=created_by,
            status='draft',
            include_vat=include_vat,
        )

        # Build line items and accumulate the subtotal.
        subtotal = Decimal('0')
        for item in items_data:
            qty = Decimal(str(item['quantity']))
            price = Decimal(str(item['unit_price']))
            total = qty * price
            InvoiceItem.objects.create(
                invoice=invoice,
                description=item['description'],
                quantity=qty,
                unit_price=price,
                total=total,
            )
            subtotal += total

        # Apply VAT only when requested.
        vat = get_vat_rate() if include_vat else Decimal('0')
        tax = subtotal * vat
        invoice.subtotal = subtotal
        invoice.tax_amount = tax
        invoice.total_amount = subtotal + tax
        invoice.save(update_fields=['subtotal', 'tax_amount', 'total_amount'])
        return invoice

    # -------------------------------------------------------------------------
    # Recalculation
    # -------------------------------------------------------------------------
    @staticmethod
    def recalculate(invoice):
        """
        Recompute subtotal, tax, and total from the current line items.

        Called after any change to the invoice's items (add, delete, edit).
        Saves only the three monetary fields to avoid touching status/timestamps.
        """
        subtotal = sum(i.total for i in invoice.items.all())
        vat = get_vat_rate() if invoice.include_vat else Decimal('0')

        invoice.subtotal = subtotal
        invoice.tax_amount = subtotal * vat
        invoice.total_amount = subtotal + invoice.tax_amount
        invoice.save(update_fields=['subtotal', 'tax_amount', 'total_amount'])

    # -------------------------------------------------------------------------
    # Payment recording (auto-issues receipt when fully paid)
    # -------------------------------------------------------------------------
    @staticmethod
    def record_payment(
        invoice, amount, method, date, reference='', notes='', recorded_by=None,
        *,
        # Optional transaction metadata used on the auto-generated receipt:
        transaction_id='',
        transaction_fee=0,
        source_account='',
        destination_account='',
        payment_datetime=None,
    ):
        """
        Record a payment against an invoice and update the invoice status.

        Status transitions:
          - amount_paid >= total_amount  → 'paid'      (triggers receipt)
          - 0 < amount_paid < total      → 'partial'   (no receipt)

        When the invoice becomes fully paid, a Receipt is created carrying
        the supplied transaction metadata (transaction_id, fee, source /
        destination accounts, exact datetime). Receipt failures are logged
        but never block the payment from being saved.

        Returns:
            The newly created Payment instance.
        """
        payment = Payment.objects.create(
            invoice=invoice,
            amount=amount,
            method=method,
            date=date,
            reference=reference,
            notes=notes,
            recorded_by=recorded_by,
        )

        # Recompute from actual payment rows (single source of truth).
        invoice.amount_paid = sum(p.amount for p in invoice.payments.all())
        fully_paid = invoice.amount_paid >= invoice.total_amount

        if fully_paid:
            invoice.status = 'paid'
        elif invoice.amount_paid > 0:
            invoice.status = 'partial'
        invoice.save(update_fields=['amount_paid', 'status'])

        # Auto-issue a receipt the moment the invoice becomes fully paid.
        if fully_paid:
            try:
                ReceiptService.create_from_payment(
                    payment,
                    transaction_id=transaction_id,
                    transaction_fee=transaction_fee or Decimal('0'),
                    source_account=source_account,
                    destination_account=destination_account,
                    payment_datetime=payment_datetime,
                    issued_by=recorded_by,
                )
                logger.info(
                    f"Auto-issued receipt for payment on {invoice.invoice_number}."
                )
            except Exception as e:
                # Never block payment recording because of a receipt issue.
                logger.exception(
                    f"Failed to auto-issue receipt for "
                    f"{invoice.invoice_number}: {e}"
                )

        notify_payment_received(payment)
        return payment

    # -------------------------------------------------------------------------
    # Issuance (draft → issued)
    # -------------------------------------------------------------------------
    @staticmethod
    def issue(invoice):
        """
        Move a draft invoice to 'issued', ensuring totals are consistent
        with the underlying line items before sending the notification.

        If stored totals are out of sync, they are corrected and a warning
        is logged so the mismatch can be audited later.

        Raises:
            ValueError: if the invoice is not in 'draft' status.
        """
        if invoice.status != 'draft':
            raise ValueError('Only draft invoices can be issued.')

        # Recompute to guarantee the saved figures match the line items.
        subtotal = sum(item.total for item in invoice.items.all())
        vat = get_vat_rate() if invoice.include_vat else Decimal('0')
        tax = subtotal * vat
        total = subtotal + tax

        if (
            invoice.subtotal != subtotal
            or invoice.tax_amount != tax
            or invoice.total_amount != total
        ):
            old = (invoice.subtotal, invoice.tax_amount, invoice.total_amount)
            invoice.subtotal = subtotal
            invoice.tax_amount = tax
            invoice.total_amount = total
            invoice.save(update_fields=['subtotal', 'tax_amount', 'total_amount'])
            logger.warning(
                f"Invoice {invoice.invoice_number} totals were inconsistent and "
                f"have been corrected. Old (subtotal, tax, total)={old} → "
                f"({subtotal}, {tax}, {total})."
            )

        invoice.status = 'issued'
        invoice.save(update_fields=['status'])
        notify_invoice_issued(invoice)


# =============================================================================
# RECEIPT SERVICE
# =============================================================================
class ReceiptService:
    """
    Creates and manages payment receipts.

    A receipt is auto-generated when an invoice becomes fully paid (see
    InvoiceService.record_payment). It captures transaction-level details
    so the printed PDF matches the actual money movement (bank, mobile
    money, processor fee, transaction ID, etc.).
    """

    @staticmethod
    @transaction.atomic
    def create_from_payment(
        payment,
        *,
        transaction_id='',
        transaction_fee=0,
        source_account='',
        destination_account='',
        payment_datetime=None,
        description='',
        reference='',
        issued_by=None,
    ):
        """
        Create a receipt for a given payment. Idempotent — if the payment
        already has a receipt, that receipt is returned instead of erroring.

        Args:
            payment:              Payment instance (linked to an Invoice).
            transaction_id:       External processor / bank transaction ref.
            transaction_fee:      Processor fee (paid by payer, not from invoice).
            source_account:       Payer's account, e.g. '0888606770 - Daniel Phiri'.
            destination_account:  Company account, e.g. 'NBM - 1012900798'.
            payment_datetime:     Exact datetime (defaults to payment.date 00:00).
            description:          Short line description (defaults to first item).
            reference:            Reference shown on the receipt
                                  (defaults to the invoice number).
            issued_by:            User who recorded the payment.

        Returns:
            The (newly created or existing) Receipt instance.
        """
        # Idempotency: return the existing receipt if one already exists.
        if hasattr(payment, 'receipt'):
            return payment.receipt

        invoice = payment.invoice
        receipt = Receipt.objects.create(
            payment=payment,
            invoice=invoice,
            reference=reference or invoice.invoice_number,
            description=description,
            transaction_id=transaction_id,
            transaction_fee=transaction_fee or Decimal('0'),
            source_account=source_account,
            destination_account=destination_account,
            payment_datetime=payment_datetime,
            issued_by=issued_by,
        )
        logger.info(
            f"Created receipt {receipt.receipt_number} for "
            f"invoice {invoice.invoice_number} (payment {payment.pk})."
        )
        return receipt

    @staticmethod
    def issue_now(
        invoice,
        *,
        transaction_id='',
        transaction_fee=0,
        source_account='',
        destination_account='',
        payment_datetime=None,
        reference='',
        description='',
        issued_by=None,
    ):
        """
        Manually issue a receipt for an already-paid invoice.

        Useful for:
          - Backfilling legacy invoices paid before auto-receipts existed.
          - Correcting historical imports.

        Uses the most recent payment on the invoice as the basis for the
        receipt's amount, method, etc.

        Raises:
            ValueError: invoice not paid, already has a receipt,
                        or has no payments to base a receipt on.
        """
        if invoice.status != 'paid':
            raise ValueError('Only fully paid invoices can be receipted.')
        if hasattr(invoice, 'receipt'):
            raise ValueError('This invoice already has a receipt.')

        last_payment = invoice.payments.order_by('-date', '-pk').first()
        if not last_payment:
            raise ValueError('Invoice has no payments to base a receipt on.')

        return ReceiptService.create_from_payment(
            last_payment,
            transaction_id=transaction_id,
            transaction_fee=transaction_fee,
            source_account=source_account,
            destination_account=destination_account,
            payment_datetime=payment_datetime,
            reference=reference,
            description=description,
            issued_by=issued_by,
        )


# =============================================================================
# QUOTATION SERVICE
# =============================================================================
class QuotationService:
    """
    Handles quotation lifecycle:
      create → send → approve → convert to invoice.
    Also exposes helpers for Quill (rich text) JSON handling.
    """

    # -------------------------------------------------------------------------
    # Quill helpers
    # -------------------------------------------------------------------------
    @staticmethod
    def _ensure_quill_json(value):
        """
        Convert a plain-text string into Quill JSON if it isn't already JSON.

        Quill fields expect a JSON string like {"html": "...", "delta": ""}.
        Passing plain text into a QuillField would otherwise break rendering.
        """
        if value is None:
            return None
        if isinstance(value, str) and not value.strip().startswith('{'):
            return json.dumps({"html": f"<p>{value}</p>", "delta": ""})
        return value

    @staticmethod
    def _extract_quill_html(value):
        """
        Safely extract HTML content from a Quill field or a plain string.

        Returns a string (HTML) suitable for concatenation into notes.
        """
        if value is None:
            return ''
        if hasattr(value, 'html'):
            return value.html
        return str(value)

    # -------------------------------------------------------------------------
    # Creation
    # -------------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def create_quotation(
        client, items_data, issue_date, valid_until,
        notes='', created_by=None, include_vat=True,
    ):
        """
        Create a draft quotation with line items.

        Args:
            client:       ClientOrganization instance.
            items_data:   List of dicts: {description, quantity, unit_price}.
            issue_date:   date — issue date.
            valid_until:  date — validity end date.
            notes:        Free-text (converted to Quill JSON).
            created_by:   User instance or None.
            include_vat:  bool — apply VAT or not.

        Returns:
            The saved Quotation instance.
        """
        notes_json = QuotationService._ensure_quill_json(notes)
        quotation = Quotation.objects.create(
            client=client,
            issue_date=issue_date,
            valid_until=valid_until,
            notes=notes_json,
            created_by=created_by,
            status='draft',
            include_vat=include_vat,
        )

        subtotal = Decimal('0')
        for item in items_data:
            qty = Decimal(str(item['quantity']))
            price = Decimal(str(item['unit_price']))
            total = qty * price
            QuotationItem.objects.create(
                quotation=quotation,
                description=item['description'],
                quantity=qty,
                unit_price=price,
                total=total,
            )
            subtotal += total

        vat = get_vat_rate() if include_vat else Decimal('0')
        tax = subtotal * vat
        quotation.subtotal = subtotal
        quotation.tax_amount = tax
        quotation.total_amount = subtotal + tax
        quotation.save(update_fields=['subtotal', 'tax_amount', 'total_amount'])
        return quotation

    # -------------------------------------------------------------------------
    # Recalculation
    # -------------------------------------------------------------------------
    @staticmethod
    def recalculate(quotation):
        """Recompute subtotal, tax, and total from the current line items."""
        subtotal = sum(i.total for i in quotation.items.all())
        vat = get_vat_rate() if quotation.include_vat else Decimal('0')

        quotation.subtotal = subtotal
        quotation.tax_amount = subtotal * vat
        quotation.total_amount = subtotal + quotation.tax_amount
        quotation.save(update_fields=['subtotal', 'tax_amount', 'total_amount'])

    # -------------------------------------------------------------------------
    # Workflow transitions
    # -------------------------------------------------------------------------
    @staticmethod
    def send(quotation):
        """
        Move quotation from 'draft' to 'sent'.

        Raises:
            ValueError: if the quotation is not a draft.
        """
        if quotation.status != 'draft':
            raise ValueError('Only draft quotations can be sent.')
        quotation.status = 'sent'
        quotation.save(update_fields=['status'])

    @staticmethod
    def approve(quotation):
        """
        Move quotation from 'sent' to 'approved'.

        Raises:
            ValueError: if the quotation is not currently 'sent'.
        """
        if quotation.status != 'sent':
            raise ValueError('Only sent quotations can be approved.')
        quotation.status = 'approved'
        quotation.save(update_fields=['status'])

    # -------------------------------------------------------------------------
    # Convert approved quotation → draft invoice
    # -------------------------------------------------------------------------
    @staticmethod
    def convert_to_invoice(quotation, created_by=None):
        """
        Convert an approved quotation into a draft invoice.

        Behaviour:
          - Copies line items verbatim (description, quantity, price, total).
          - Copies monetary totals from the quotation.
          - Copies the include_vat flag so VAT behaviour carries across.
          - Merges the quotation's notes with the client's approval feedback
            and re-encodes the result as Quill JSON for the invoice.
          - Marks the quotation as 'converted'.

        Raises:
            ValueError: if the quotation is not in 'approved' state.

        Returns:
            The newly created Invoice instance (status='draft').
        """
        if quotation.status != 'approved':
            raise ValueError(
                'Quotation must be approved by client before conversion to invoice.'
            )

        # Merge notes + client feedback into a single HTML block.
        notes_parts = []
        if quotation.notes:
            notes_parts.append(QuotationService._extract_quill_html(quotation.notes))
        if quotation.client_feedback:
            notes_parts.append(
                f"<strong>Client feedback during approval:</strong><br>"
                f"{quotation.client_feedback}"
            )
        notes_content = "\n\n".join(notes_parts) if notes_parts else ""
        notes_json = QuotationService._ensure_quill_json(notes_content)

        invoice = Invoice.objects.create(
            client=quotation.client,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            notes=notes_json,
            created_by=created_by,
            status='draft',
            include_vat=quotation.include_vat,
        )

        # Copy the line items.
        for q_item in quotation.items.all():
            InvoiceItem.objects.create(
                invoice=invoice,
                description=q_item.description,
                quantity=q_item.quantity,
                unit_price=q_item.unit_price,
                total=q_item.total,
            )

        # Copy monetary totals directly (avoids a second DB round-trip).
        invoice.subtotal = quotation.subtotal
        invoice.tax_amount = quotation.tax_amount
        invoice.total_amount = quotation.total_amount
        invoice.save()

        quotation.status = 'converted'
        quotation.save(update_fields=['status'])
        return invoice