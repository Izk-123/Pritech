from django.conf import settings
from django.db import transaction
from .models import Invoice, InvoiceItem, Payment
from infrastructure.notifications import notify_invoice_issued, notify_payment_received


class InvoiceService:
    @staticmethod
    @transaction.atomic
    def create_invoice(client, items_data, issue_date, due_date, ticket=None, notes='', created_by=None):
        invoice = Invoice.objects.create(
            client=client, ticket=ticket, issue_date=issue_date,
            due_date=due_date, notes=notes, created_by=created_by, status='draft'
        )
        subtotal = 0
        for item in items_data:
            qty = item['quantity']
            price = item['unit_price']
            total = qty * price
            InvoiceItem.objects.create(
                invoice=invoice, description=item['description'],
                quantity=qty, unit_price=price, total=total
            )
            subtotal += total
        vat = getattr(settings, 'VAT_RATE', 0.165)
        tax = subtotal * vat
        invoice.subtotal = subtotal
        invoice.tax_amount = tax
        invoice.total_amount = subtotal + tax
        invoice.save(update_fields=['subtotal', 'tax_amount', 'total_amount'])
        return invoice

    @staticmethod
    def recalculate(invoice):
        subtotal = sum(i.total for i in invoice.items.all())
        vat = getattr(settings, 'VAT_RATE', 0.165)
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
