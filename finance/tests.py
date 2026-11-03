# finance/tests.py
"""
Finance app tests
-----------------
Covers:
  - Partial payment → no receipt
  - Full payment → receipt auto-issued
  - Idempotency (recording twice doesn't duplicate)
  - Receipt number format (REC-XXXX)
  - Receipt PDF renders
  - Quotation → Invoice conversion
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clients.models import ClientOrganization
from finance.models import (
    Invoice, InvoiceItem, Payment, Receipt,
    Quotation, QuotationItem,
)
from finance.services import InvoiceService, ReceiptService, QuotationService


User = get_user_model()


class InvoiceReceiptTestCase(TestCase):
    """Fixtures for all receipt-related tests."""

    def setUp(self):
        self.finance_user = User.objects.create_user(
            email='finance@test.com',
            password='testpass123',
            first_name='Finance',
            last_name='Officer',
            is_staff=True,
        )
        self.client_org = ClientOrganization.objects.create(
            name='Acme Corp',
            email='billing@acme.test',
            phone='+265991234567',
        )
        # Draft invoice with one item, total = 115,000 (100k + 15% VAT)
        self.invoice = InvoiceService.create_invoice(
            client=self.client_org,
            items_data=[{
                'description': 'Network setup',
                'quantity': Decimal('1'),
                'unit_price': Decimal('100000.00'),
            }],
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            created_by=self.finance_user,
            include_vat=True,
        )
        InvoiceService.issue(self.invoice)

    # ------------------------------------------------------------------
    # 1. Partial payment → NO receipt
    # ------------------------------------------------------------------
    def test_partial_payment_does_not_create_receipt(self):
        InvoiceService.record_payment(
            invoice=self.invoice,
            amount=Decimal('50000.00'),
            method='bank_transfer',
            date=date.today(),
            recorded_by=self.finance_user,
        )
        self.invoice.refresh_from_db()

        self.assertEqual(self.invoice.status, 'partial')
        self.assertFalse(
            Receipt.objects.filter(invoice=self.invoice).exists(),
            "Partial payment should NOT create a receipt",
        )

    # ------------------------------------------------------------------
    # 2. Full payment → receipt auto-issued
    # ------------------------------------------------------------------
    def test_full_payment_creates_receipt(self):
        InvoiceService.record_payment(
            invoice=self.invoice,
            amount=Decimal('115000.00'),
            method='bank_transfer',
            date=date.today(),
            reference='REF-001',
            recorded_by=self.finance_user,
            transaction_id='DK283D7BDEC',
            transaction_fee=Decimal('1700.00'),
            source_account='0888606770 - Daniel Phiri',
            destination_account='NBM - 1012900798',
        )
        self.invoice.refresh_from_db()

        self.assertEqual(self.invoice.status, 'paid')
        receipt = Receipt.objects.get(invoice=self.invoice)

        # Receipt number format
        self.assertRegex(receipt.receipt_number, r'^REC-\d{4}$')

        # Transaction metadata stored
        self.assertEqual(receipt.transaction_id, 'DK283D7BDEC')
        self.assertEqual(receipt.transaction_fee, Decimal('1700.00'))
        self.assertEqual(receipt.total_deducted, Decimal('116700.00'))
        self.assertEqual(receipt.source_account, '0888606770 - Daniel Phiri')
        self.assertEqual(receipt.destination_account, 'NBM - 1012900798')

        # Auto-populated fields
        self.assertTrue(receipt.is_paid_in_full)
        self.assertEqual(receipt.effective_reference, self.invoice.invoice_number)
        self.assertEqual(receipt.effective_description, 'Network setup')
        self.assertIsNotNone(receipt.payment_datetime)

    # ------------------------------------------------------------------
    # 3. Idempotency: recording a 2nd payment shouldn't break the receipt
    # ------------------------------------------------------------------
    def test_second_payment_does_not_duplicate_receipt(self):
        # First payment fully settles the invoice
        InvoiceService.record_payment(
            invoice=self.invoice,
            amount=Decimal('115000.00'),
            method='cash',
            date=date.today(),
            recorded_by=self.finance_user,
        )
        first_receipt = Receipt.objects.get(invoice=self.invoice)

        # Second "payment" (would normally be blocked by the view,
        # but service should still be safe)
        InvoiceService.record_payment(
            invoice=self.invoice,
            amount=Decimal('1000.00'),
            method='cash',
            date=date.today(),
            recorded_by=self.finance_user,
        )

        self.assertEqual(
            Receipt.objects.filter(invoice=self.invoice).count(), 1,
            "Invoice should still have exactly one receipt",
        )
        self.assertEqual(
            Receipt.objects.get(invoice=self.invoice).pk,
            first_receipt.pk,
            "Existing receipt should be reused (idempotent)",
        )

    # ------------------------------------------------------------------
    # 4. ReceiptService.create_from_payment is idempotent
    # ------------------------------------------------------------------
    def test_create_from_payment_is_idempotent(self):
        payment = InvoiceService.record_payment(
            invoice=self.invoice,
            amount=Decimal('115000.00'),
            method='cash',
            date=date.today(),
            recorded_by=self.finance_user,
        )
        existing = Receipt.objects.get(payment=payment)

        again = ReceiptService.create_from_payment(payment)
        self.assertEqual(again.pk, existing.pk)

    # ------------------------------------------------------------------
    # 5. issue_now for backfilling legacy invoices
    # ------------------------------------------------------------------
    def test_issue_now_backfills_legacy_invoice(self):
        # Simulate a legacy invoice paid without auto-receipt
        self.invoice.amount_paid = self.invoice.total_amount
        self.invoice.status = 'paid'
        self.invoice.save()
        Payment.objects.create(
            invoice=self.invoice,
            amount=self.invoice.total_amount,
            method='bank_transfer',
            date=date.today(),
            recorded_by=self.finance_user,
        )

        self.assertFalse(hasattr(self.invoice, 'receipt'))

        receipt = ReceiptService.issue_now(
            self.invoice, transaction_id='LEGACY-1', issued_by=self.finance_user,
        )
        self.assertRegex(receipt.receipt_number, r'^REC-\d{4}$')
        self.assertEqual(receipt.transaction_id, 'LEGACY-1')

    # ------------------------------------------------------------------
    # 6. issue_now rejects unpaid invoices
    # ------------------------------------------------------------------
    def test_issue_now_rejects_unpaid_invoice(self):
        with self.assertRaises(ValueError):
            ReceiptService.issue_now(self.invoice)


class ReceiptPDFTestCase(TestCase):
    """Receipt PDF renders without errors."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='pdf@test.com', password='x', is_staff=True,
        )
        self.client_org = ClientOrganization.objects.create(
            name='PDF Client', email='pdfclient@test.com',
        )
        self.invoice = InvoiceService.create_invoice(
            client=self.client_org,
            items_data=[{
                'description': 'Consulting',
                'quantity': Decimal('2'),
                'unit_price': Decimal('50000.00'),
            }],
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            created_by=self.user,
        )
        InvoiceService.issue(self.invoice)
        InvoiceService.record_payment(
            invoice=self.invoice,
            amount=self.invoice.total_amount,
            method='bank_transfer',
            date=date.today(),
            recorded_by=self.user,
        )
        self.receipt = Receipt.objects.get(invoice=self.invoice)

    def test_receipt_pdf_renders(self):
        from infrastructure.pdf_reportlab import (
            render_receipt_pdf, load_logo_data_uri,
        )
        from core.models import SiteConfig

        config = SiteConfig.get()
        pdf_bytes = render_receipt_pdf(
            self.receipt, config, load_logo_data_uri(),
        )
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 1000)
        # PDF magic number
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'))

    def test_receipt_pdf_direct_view(self):
        self.client.force_login(self.user)
        url = reverse('receipt_pdf_direct', args=[self.receipt.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn(
            f'receipt_{self.receipt.receipt_number}.pdf',
            response['Content-Disposition'],
        )


class QuotationConversionTestCase(TestCase):
    """Approved quotation converts to draft invoice."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='conv@test.com', password='x', is_staff=True,
        )
        self.client_org = ClientOrganization.objects.create(
            name='Conv Client', email='conv@test.com',
        )
        self.quotation = QuotationService.create_quotation(
            client=self.client_org,
            items_data=[{
                'description': 'Domain',
                'quantity': Decimal('1'),
                'unit_price': Decimal('38500.00'),
            }],
            issue_date=date.today(),
            valid_until=date.today() + timedelta(days=30),
            created_by=self.user,
        )

    def test_convert_requires_approval(self):
        with self.assertRaises(ValueError):
            QuotationService.convert_to_invoice(self.quotation)

    def test_full_workflow(self):
        QuotationService.send(self.quotation)
        QuotationService.approve(self.quotation)
        invoice = QuotationService.convert_to_invoice(
            self.quotation, created_by=self.user,
        )

        self.quotation.refresh_from_db()
        self.assertEqual(self.quotation.status, 'converted')
        self.assertEqual(invoice.status, 'draft')
        self.assertEqual(invoice.items.count(), 1)
        self.assertEqual(invoice.items.first().description, 'Domain')
        self.assertEqual(invoice.total_amount, self.quotation.total_amount)