from django.contrib import admin
from .models import Invoice, InvoiceItem, Payment, Expense

class ItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1

class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'client', 'total_amount', 'amount_paid', 'status', 'due_date')
    list_filter = ('status',)
    search_fields = ('invoice_number', 'client__name')
    inlines = [ItemInline, PaymentInline]

admin.site.register(Expense)
