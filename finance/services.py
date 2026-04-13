from datetime import date, timedelta
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from .models import Invoice, InvoiceItem, Payment, Quotation, QuotationItem
from infrastructure.notifications import notify_invoice_issued, notify_payment_received


def get_vat_rate():
    """Return VAT rate as Decimal."""
    rate = getattr(settings, 'VAT_RATE', 0.165)
    return Decimal(str(rate))


class InvoiceService:
    @staticmethod
    @transaction.atomic
    def create_invoice(client, items_data, issue_date, due_date, ticket=None, notes='', created_by=None):
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
        subtotal = sum(i.total for i in invoice.items.all())
        vat = get_vat_rate()
        invoice.subtotal = subtotal
        invoice.tax_amount = subtotal * vat
        invoice.total_amount = subtotal + invoice.tax_amount
        invoice.save(update_fields=['subtotal', 'tax_amount', 'total_amount'])

    @staticmethod
    def record_payment(invoice, amount, method, date, reference='', notes='', recorded_by=None):
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
        if invoice.status != 'draft':
            raise ValueError('Only draft invoices can be issued.')
        invoice.status = 'issued'
        invoice.save(update_fields=['status'])
        notify_invoice_issued(invoice)


class QuotationService:
    @staticmethod
    @transaction.atomic
    def create_quotation(client, items_data, issue_date, valid_until, notes='', created_by=None):
        quotation = Quotation.objects.create(
            client=client, issue_date=issue_date, valid_until=valid_until,
            notes=notes, created_by=created_by, status='draft'
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
        subtotal = sum(i.total for i in quotation.items.all())
        vat = get_vat_rate()
        quotation.subtotal = subtotal
        quotation.tax_amount = subtotal * vat
        quotation.total_amount = subtotal + quotation.tax_amount
        quotation.save(update_fields=['subtotal', 'tax_amount', 'total_amount'])

    @staticmethod
    def send(quotation):
        if quotation.status != 'draft':
            raise ValueError('Only draft quotations can be sent.')
        quotation.status = 'sent'
        quotation.save(update_fields=['status'])
        # Optionally add email notification here

    @staticmethod
    def approve(quotation):
        if quotation.status != 'sent':
            raise ValueError('Only sent quotations can be approved.')
        quotation.status = 'approved'
        quotation.save(update_fields=['status'])

    @staticmethod
    def convert_to_invoice(quotation, created_by=None):
        if quotation.status not in ['approved', 'sent']:  # allow conversion from sent as well
            raise ValueError('Quotation must be approved before conversion.')
        # Create invoice
        invoice = Invoice.objects.create(
            client=quotation.client,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),  # default 30 days
            notes=quotation.notes,
            created_by=created_by,
            status='draft'
        )
        # Copy items
        for q_item in quotation.items.all():
            InvoiceItem.objects.create(
                invoice=invoice,
                description=q_item.description,
                quantity=q_item.quantity,
                unit_price=q_item.unit_price,
                total=q_item.total
            )
        # Copy totals
        invoice.subtotal = quotation.subtotal
        invoice.tax_amount = quotation.tax_amount
        invoice.total_amount = quotation.total_amount
        invoice.save()
        # Mark quotation as converted
        quotation.status = 'converted'
        quotation.save(update_fields=['status'])
        return invoice