# finance/models.py
"""
Finance App Models
------------------
Models for invoices, payments, receipts, quotations, subscriptions, and
expenses.

Quill fields automatically convert plain text to the required JSON format
(`{"html": "...", "delta": ""}`) on save via `ensure_quill_json()`.

Model summary
-------------
- Invoice            – client billing document.
- InvoiceItem        – line item on an invoice.
- Payment            – money received against an invoice.
- Receipt            – auto-issued proof-of-payment (one per paid invoice).
- Expense            – internal cost with approval workflow.
- Quotation          – client proposal; can convert to invoice.
- QuotationItem      – line item on a quotation.
- Plan               – subscription plan (Basic, Pro, Enterprise…).
- ClientSubscription – active subscription linking a client to a plan.
"""

import json
from decimal import Decimal
from datetime import datetime, time

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django_quill.fields import QuillField
from simple_history.models import HistoricalRecords


# -----------------------------------------------------------------------------
# Helper: convert plain text → Quill JSON
# -----------------------------------------------------------------------------
def ensure_quill_json(value):
    """Convert a plain-text string to Quill JSON if it is not already JSON."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip().startswith('{'):
        return json.dumps({"html": f"<p>{value}</p>", "delta": ""})
    return value


# =============================================================================
# INVOICE
# =============================================================================
class Invoice(models.Model):
    """
    Invoice for client services.

    Lifecycle: draft → issued → partial → paid (or overdue/cancelled).
    A Receipt is auto-created when the invoice reaches 'paid'.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]

    invoice_number = models.CharField(max_length=30, unique=True, blank=True)
    client = models.ForeignKey(
        'clients.ClientOrganization',
        on_delete=models.PROTECT,
        related_name='invoices',
        db_index=True,
    )
    ticket = models.ForeignKey(
        'tickets.Ticket',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoices',
    )
    issue_date = models.DateField(db_index=True)
    due_date = models.DateField()
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True,
    )
    notes = QuillField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    subscription = models.ForeignKey(
        'ClientSubscription',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoices',
    )
    include_vat = models.BooleanField(
        default=True,
        help_text="If unchecked, VAT will not be added to this invoice.",
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.invoice_number or f"Invoice #{self.pk}"

    def save(self, *args, **kwargs):
        # Auto-generate invoice number if missing.
        if not self.invoice_number:
            last = Invoice.objects.order_by('-pk').first()
            num = (last.pk + 1) if last else 1
            self.invoice_number = f"INV-{num:04d}"
        # Normalise notes into Quill-compatible JSON.
        self.notes = ensure_quill_json(self.notes)
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Convenience properties used in templates
    # ------------------------------------------------------------------
    @property
    def balance_due(self):
        return self.total_amount - self.amount_paid

    @property
    def status_color(self):
        """Bootstrap colour class for status badges."""
        colors = {
            'draft': 'secondary',
            'issued': 'primary',
            'partial': 'warning',
            'paid': 'success',
            'overdue': 'danger',
            'cancelled': 'secondary',
        }
        return colors.get(self.status, 'secondary')


# =============================================================================
# INVOICE ITEM
# =============================================================================
class InvoiceItem(models.Model):
    """Line item belonging to an invoice."""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=1,
        validators=[MinValueValidator(Decimal('0'))],
    )
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
    )
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} – {self.total}"


# =============================================================================
# PAYMENT
# =============================================================================
class Payment(models.Model):
    """A payment recorded against an invoice."""
    METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('cheque', 'Cheque'),
        ('other', 'Other'),
    ]

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name='payments', db_index=True,
    )
    amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    reference = models.CharField(max_length=100, blank=True)
    date = models.DateField()
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Payment of {self.amount} for {self.invoice.invoice_number}"


# =============================================================================
# RECEIPT
# =============================================================================
class Receipt(models.Model):
    """
    Official payment receipt for an invoice.

    Auto-created by `InvoiceService.record_payment()` when an invoice becomes
    fully paid. Holds transaction-level details (bank/processor ref, fees,
    source/destination accounts, exact datetime) shown on the printed PDF.
    """
    receipt_number = models.CharField(max_length=30, unique=True, blank=True)

    # One receipt per payment (guarantees idempotency via the DB).
    payment = models.OneToOneField(
        Payment, on_delete=models.CASCADE, related_name='receipt',
    )
    # And one receipt per invoice (an invoice can only be paid once in full).
    invoice = models.OneToOneField(
        Invoice, on_delete=models.PROTECT, related_name='receipt',
    )

    # Document-level metadata
    reference = models.CharField(
        max_length=100, blank=True,
        help_text="Reference shown on receipt (defaults to invoice number).",
    )
    description = models.CharField(
        max_length=300, blank=True,
        help_text="Short line description (defaults to first invoice item).",
    )

    # Transaction details
    transaction_id = models.CharField(max_length=100, blank=True)
    transaction_fee = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text="Processor fee paid by payer (does not reduce invoice amount).",
    )
    source_account = models.CharField(
        max_length=255, blank=True,
        help_text="e.g. '0888606770 - Daniel Joseph Phiri'",
    )
    destination_account = models.CharField(
        max_length=255, blank=True,
        help_text="e.g. 'National Bank of Malawi - Account 1012900798'",
    )
    payment_datetime = models.DateTimeField(
        null=True, blank=True,
        help_text="Exact date & time of payment (defaults to payment.date at 00:00).",
    )

    # Issuer / audit
    issued_at = models.DateTimeField(auto_now_add=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ['-issued_at']

    def __str__(self):
        return self.receipt_number or f"Receipt #{self.pk}"

    def save(self, *args, **kwargs):
        # Auto-generate receipt number (REC-0001, REC-0002, …)
        if not self.receipt_number:
            last = Receipt.objects.order_by('-pk').first()
            num = (last.pk + 1) if last else 1
            self.receipt_number = f"REC-{num:04d}"

        # Default payment_datetime from the payment's date at 00:00 local time.
        if not self.payment_datetime and self.payment_id:
            naive = datetime.combine(self.payment.date, time.min)
            self.payment_datetime = timezone.make_aware(
                naive, timezone.get_current_timezone(),
            )

        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Convenience properties used in templates / PDF
    # ------------------------------------------------------------------
    @property
    def total_deducted(self):
        """What the payer actually paid = payment amount + processor fee."""
        return self.payment.amount + self.transaction_fee

    @property
    def is_paid_in_full(self):
        return self.payment.invoice.status == 'paid'

    @property
    def effective_reference(self):
        return self.reference or self.invoice.invoice_number

    @property
    def effective_description(self):
        if self.description:
            return self.description
        first = self.invoice.items.first()
        return first.description if first else f"Payment for {self.invoice.invoice_number}"


# =============================================================================
# EXPENSE
# =============================================================================
class Expense(models.Model):
    """Internal cost record with an approval workflow."""
    CATEGORY_CHOICES = [
        ('salaries', 'Salaries'),
        ('equipment', 'Equipment'),
        ('transport', 'Transport'),
        ('utilities', 'Utilities'),
        ('marketing', 'Marketing'),
        ('other', 'Other'),
    ]
    EXPENSE_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    category = models.CharField(
        max_length=50, choices=CATEGORY_CHOICES, db_index=True,
    )
    description = models.CharField(max_length=300)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    date = models.DateField(db_index=True)
    receipt = models.FileField(upload_to='receipts/', null=True, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, choices=EXPENSE_STATUS_CHOICES, default='pending',
        db_index=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_expenses',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.description} - {self.amount} ({self.get_status_display()})"


# =============================================================================
# QUOTATION
# =============================================================================
class Quotation(models.Model):
    """Quotation sent to a client; can be approved and converted to invoice."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
        ('converted', 'Converted'),
    ]

    quotation_number = models.CharField(max_length=30, unique=True, blank=True)
    client = models.ForeignKey(
        'clients.ClientOrganization',
        on_delete=models.PROTECT,
        related_name='quotations',
        db_index=True,
    )
    issue_date = models.DateField()
    valid_until = models.DateField()
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True,
    )
    notes = QuillField(blank=True)
    client_feedback = models.TextField(
        blank=True,
        help_text="Client's rejection reason or change request.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    include_vat = models.BooleanField(
        default=True,
        help_text="If unchecked, VAT will not be added to this quotation.",
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.quotation_number or f"Quotation #{self.pk}"

    def save(self, *args, **kwargs):
        # Auto-generate quotation number if missing.
        if not self.quotation_number:
            last = Quotation.objects.order_by('-pk').first()
            num = (last.pk + 1) if last else 1
            self.quotation_number = f"QUO-{num:04d}"
        # Normalise notes into Quill-compatible JSON.
        self.notes = ensure_quill_json(self.notes)
        super().save(*args, **kwargs)


# =============================================================================
# QUOTATION ITEM
# =============================================================================
class QuotationItem(models.Model):
    """Line item belonging to a quotation."""
    quotation = models.ForeignKey(
        Quotation, on_delete=models.CASCADE, related_name='items',
    )
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=1,
        validators=[MinValueValidator(Decimal('0'))],
    )
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
    )
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} – {self.total}"


# =============================================================================
# SUBSCRIPTION PLAN
# =============================================================================
class Plan(models.Model):
    """A subscription plan (e.g. Basic, Pro, Enterprise)."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    monthly_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
    )
    features = models.JSONField(
        default=dict,
        help_text="Key-value store of included features.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['monthly_price']

    def __str__(self):
        return f"{self.name} - {self.monthly_price}"


# =============================================================================
# CLIENT SUBSCRIPTION
# =============================================================================
class ClientSubscription(models.Model):
    """Active subscription linking a client to a plan."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('cancelled', 'Cancelled'),
        ('trialing', 'Trialing'),
        ('incomplete', 'Incomplete'),
    ]

    client = models.OneToOneField(
        'clients.ClientOrganization',
        on_delete=models.CASCADE,
        related_name='subscription',
        db_index=True,
    )
    plan = models.ForeignKey(
        Plan, on_delete=models.PROTECT, related_name='subscriptions',
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='active', db_index=True,
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    trial_end_date = models.DateField(null=True, blank=True)
    current_period_start = models.DateField()
    current_period_end = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.client.name} - {self.plan.name} ({self.status})"