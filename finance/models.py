from django.db import models
from django.conf import settings


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'), ('issued', 'Issued'),
        ('partial', 'Partially Paid'), ('paid', 'Paid'),
        ('overdue', 'Overdue'), ('cancelled', 'Cancelled'),
    ]
    invoice_number = models.CharField(max_length=30, unique=True, blank=True)
    client = models.ForeignKey('clients.ClientOrganization', on_delete=models.PROTECT, related_name='invoices')
    ticket = models.ForeignKey('tickets.Ticket', on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    issue_date = models.DateField()
    due_date = models.DateField()
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.invoice_number or f"Invoice #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            last = Invoice.objects.order_by('-pk').first()
            num = (last.pk + 1) if last else 1
            self.invoice_number = f"INV-{num:04d}"
        super().save(*args, **kwargs)

    @property
    def balance_due(self):
        return self.total_amount - self.amount_paid

    @property
    def status_color(self):
        return {
            'draft': 'gray', 'issued': 'blue', 'partial': 'amber',
            'paid': 'green', 'overdue': 'red', 'cancelled': 'gray'
        }.get(self.status, 'gray')


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class Payment(models.Model):
    METHOD_CHOICES = [
        ('cash', 'Cash'), ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'), ('cheque', 'Cheque'), ('other', 'Other'),
    ]
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    reference = models.CharField(max_length=100, blank=True)
    date = models.DateField()
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']


class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('salaries', 'Salaries'), ('equipment', 'Equipment'), ('transport', 'Transport'),
        ('utilities', 'Utilities'), ('marketing', 'Marketing'), ('other', 'Other'),
    ]
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date = models.DateField()
    receipt = models.FileField(upload_to='receipts/', null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
