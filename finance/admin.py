from django.contrib import admin
from .models import Invoice, InvoiceItem, Payment, Expense, Quotation, QuotationItem

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
    

class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 1

@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ('quotation_number', 'client', 'total_amount', 'status', 'valid_until')
    list_filter = ('status',)
    search_fields = ('quotation_number', 'client__name')
    inlines = [QuotationItemInline]

admin.site.register(Expense)
