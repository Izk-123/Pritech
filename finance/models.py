# finance/models.py
"""
Finance App Models
------------------
Handles invoices, payments, expenses, quotations, subscription plans,
and client subscriptions. All Quill fields automatically convert plain text
to the required JSON format (`{"html": "...", "delta": ""}`) on save.
"""

import json
from decimal import Decimal
from datetime import date, timedelta

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django_quill.fields import QuillField
from simple_history.models import HistoricalRecords


# -----------------------------------------------------------------------------
# Helper function to convert plain text to Quill JSON
# -----------------------------------------------------------------------------
def ensure_quill_json(value):
    """Convert a plain text string to Quill JSON if it is not already JSON."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip().startswith('{'):
        return json.dumps({"html": f"<p>{value}</p>", "delta": ""})
    return value


# -----------------------------------------------------------------------------
# Invoice & Related Models
# -----------------------------------------------------------------------------
class Invoice(models.Model):
    """Invoice for client services."""
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
        db_index=True
    )
    ticket = models.ForeignKey(
        'tickets.Ticket',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoices'
    )
    issue_date = models.DateField(db_index=True)
    due_date = models.DateField()
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
    notes = QuillField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    subscription = models.ForeignKey(
        'ClientSubscription',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoices'
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.invoice_number or f"Invoice #{self.pk}"

    def save(self, *args, **kwargs):
        # Auto-generate invoice number if missing
        if not self.invoice_number:
            last = Invoice.objects.order_by('-pk').first()
            num = (last.pk + 1) if last else 1
            self.invoice_number = f"INV-{num:04d}"
        # Convert plain text notes to Quill JSON
        self.notes = ensure_quill_json(self.notes)
        super().save(*args, **kwargs)

    @property
    def balance_due(self):
        return self.total_amount - self.amount_paid

    @property
    def status_color(self):
        """Returns Bootstrap color class for status badges."""
        colors = {
            'draft': 'secondary',
            'issued': 'primary',
            'partial': 'warning',
            'paid': 'success',
            'overdue': 'danger',
            'cancelled': 'secondary',
        }
        return colors.get(self.status, 'secondary')


class InvoiceItem(models.Model):
    """Line item belonging to an invoice."""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1,
                                   validators=[MinValueValidator(Decimal('0'))])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2,
                                     validators=[MinValueValidator(Decimal('0'))])
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} – {self.total}"


class Payment(models.Model):
    """Payment recorded against an invoice."""
    METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('cheque', 'Cheque'),
        ('other', 'Other'),
    ]
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments', db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2,
                                 validators=[MinValueValidator(Decimal('0.01'))])
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    reference = models.CharField(max_length=100, blank=True)
    date = models.DateField()
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Payment of {self.amount} for {self.invoice.invoice_number}"


class Expense(models.Model):
    """Expense record with approval workflow."""
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
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, db_index=True)
    description = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=14, decimal_places=2,
                                 validators=[MinValueValidator(Decimal('0.01'))])
    date = models.DateField(db_index=True)
    receipt = models.FileField(upload_to='receipts/', null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=EXPENSE_STATUS_CHOICES, default='pending', db_index=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='approved_expenses')
    approved_at = models.DateTimeField(null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.description} - {self.amount} ({self.get_status_display()})"


# -----------------------------------------------------------------------------
# Quotation Models
# -----------------------------------------------------------------------------
class Quotation(models.Model):
    """Quotation sent to client; can be approved and converted to invoice."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
        ('converted', 'Converted'),
    ]
    quotation_number = models.CharField(max_length=30, unique=True, blank=True)
    client = models.ForeignKey('clients.ClientOrganization', on_delete=models.PROTECT,
                               related_name='quotations', db_index=True)
    issue_date = models.DateField()
    valid_until = models.DateField()
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
    notes = QuillField(blank=True)
    client_feedback = models.TextField(blank=True, help_text="Client's rejection reason or change request")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.quotation_number or f"Quotation #{self.pk}"

    def save(self, *args, **kwargs):
        # Auto-generate quotation number if missing
        if not self.quotation_number:
            last = Quotation.objects.order_by('-pk').first()
            num = (last.pk + 1) if last else 1
            self.quotation_number = f"QUO-{num:04d}"
        # Convert plain text notes to Quill JSON
        self.notes = ensure_quill_json(self.notes)
        super().save(*args, **kwargs)


class QuotationItem(models.Model):
    """Line item belonging to a quotation."""
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1,
                                   validators=[MinValueValidator(Decimal('0'))])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2,
                                     validators=[MinValueValidator(Decimal('0'))])
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} – {self.total}"


# -----------------------------------------------------------------------------
# Subscription Models
# -----------------------------------------------------------------------------
class Plan(models.Model):
    """Subscription plan (e.g., Basic, Pro, Enterprise)."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2,
                                        validators=[MinValueValidator(Decimal('0'))])
    features = models.JSONField(default=dict, help_text="Key‑value store of included features")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['monthly_price']

    def __str__(self):
        return f"{self.name} - {self.monthly_price}"


class ClientSubscription(models.Model):
    """Active subscription linking a client to a plan."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('cancelled', 'Cancelled'),
        ('trialing', 'Trialing'),
        ('incomplete', 'Incomplete'),
    ]
    client = models.OneToOneField('clients.ClientOrganization', on_delete=models.CASCADE,
                                  related_name='subscription', db_index=True)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
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