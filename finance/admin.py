from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action
from .models import Invoice, InvoiceItem, Payment, Expense, Quotation, QuotationItem


class InvoiceItemInline(TabularInline):
    model = InvoiceItem
    extra = 1
    fields = ('description', 'quantity', 'unit_price', 'total')
    readonly_fields = ('total',)


class PaymentInline(TabularInline):
    model = Payment
    extra = 0
    fields = ('amount', 'method', 'reference', 'date', 'notes')
    readonly_fields = ('created_at',)


@admin.register(Invoice)
class InvoiceAdmin(ModelAdmin):
    list_display = ('invoice_number', 'client', 'total_amount', 'amount_paid', 'status', 'due_date')
    list_filter = ('status', 'issue_date', 'due_date')
    search_fields = ('invoice_number', 'client__name')
    readonly_fields = ('invoice_number', 'subtotal', 'tax_amount', 'total_amount', 'amount_paid', 'created_at')
    inlines = [InvoiceItemInline, PaymentInline]
    actions = ['mark_as_issued', 'mark_as_paid']

    fieldsets = (
        (None, {'fields': ('invoice_number', 'client', 'ticket')}),
        ('Dates', {'fields': ('issue_date', 'due_date')}),
        ('Financials', {'fields': ('subtotal', 'tax_amount', 'total_amount', 'amount_paid', 'status')}),
        ('Notes', {'fields': ('notes',), 'classes': ('collapse',)}),
    )

    @action(description="Mark selected invoices as Issued")
    def mark_as_issued(self, request, queryset):
        queryset.update(status='issued')

    @action(description="Mark selected invoices as Paid")
    def mark_as_paid(self, request, queryset):
        queryset.update(status='paid')


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ('invoice', 'amount', 'method', 'date', 'reference')
    list_filter = ('method', 'date')
    search_fields = ('invoice__invoice_number', 'reference')
    readonly_fields = ('created_at',)


@admin.register(Expense)
class ExpenseAdmin(ModelAdmin):
    list_display = ('category', 'description', 'amount', 'date', 'receipt_link')
    list_filter = ('category', 'date')
    search_fields = ('description',)
    readonly_fields = ('created_at',)

    def receipt_link(self, obj):
        if obj.receipt:
            return format_html('<a href="{}" target="_blank">View receipt</a>', obj.receipt.url)
        return "-"
    receipt_link.short_description = "Receipt"


class QuotationItemInline(TabularInline):
    model = QuotationItem
    extra = 1
    fields = ('description', 'quantity', 'unit_price', 'total')
    readonly_fields = ('total',)


@admin.register(Quotation)
class QuotationAdmin(ModelAdmin):
    list_display = ('quotation_number', 'client', 'status', 'total_amount', 'client_feedback')
    list_filter = ('status', 'issue_date')
    search_fields = ('quotation_number', 'client__name')
    readonly_fields = ('quotation_number', 'subtotal', 'tax_amount', 'total_amount', 'created_at')
    inlines = [QuotationItemInline]
    actions = ['send_quotation', 'approve_quotation']

    @action(description="Send selected quotations")
    def send_quotation(self, request, queryset):
        queryset.update(status='sent')

    @action(description="Approve selected quotations")
    def approve_quotation(self, request, queryset):
        queryset.update(status='approved')