# finance/admin.py
"""
Finance App Admin Configuration
-------------------------------
Registers all finance models with Unfold's ModelAdmin for a modern interface.
Includes Invoice, Quotation, Expense, Payment, Plan, ClientSubscription,
and their respective line items. Also integrates historical records if simple_history is used.
"""

from unfold.admin import ModelAdmin
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    Invoice, InvoiceItem, Payment, Quotation, QuotationItem,
    Expense, Plan, ClientSubscription,
)


@admin.register(Invoice)
class InvoiceAdmin(ModelAdmin, SimpleHistoryAdmin):
    """Admin for invoices with history tracking."""
    list_display = ('invoice_number', 'client', 'total_amount', 'status', 'issue_date', 'due_date')
    list_filter = ('status', 'issue_date', 'client')
    search_fields = ('invoice_number', 'client__name')
    readonly_fields = ('invoice_number', 'created_at', 'history')
    fieldsets = (
        (None, {'fields': ('invoice_number', 'client', 'ticket', 'status')}),
        ('Dates', {'fields': ('issue_date', 'due_date')}),
        ('Amounts', {'fields': ('subtotal', 'tax_amount', 'total_amount', 'amount_paid')}),
        ('Notes', {'fields': ('notes',)}),
        ('System', {'fields': ('created_by', 'created_at', 'history')}),
    )
    raw_id_fields = ('client', 'ticket', 'created_by')


@admin.register(InvoiceItem)
class InvoiceItemAdmin(ModelAdmin):
    """Inline‑like admin for invoice line items (standalone)."""
    list_display = ('invoice', 'description', 'quantity', 'unit_price', 'total')
    search_fields = ('description', 'invoice__invoice_number')
    list_filter = ('invoice__status',)
    raw_id_fields = ('invoice',)


@admin.register(Payment)
class PaymentAdmin(ModelAdmin, SimpleHistoryAdmin):
    """Admin for payments recorded against invoices."""
    list_display = ('invoice', 'amount', 'method', 'date', 'recorded_by')
    list_filter = ('method', 'date')
    search_fields = ('invoice__invoice_number', 'reference')
    raw_id_fields = ('invoice', 'recorded_by')


@admin.register(Quotation)
class QuotationAdmin(ModelAdmin, SimpleHistoryAdmin):
    """Admin for quotations with status workflow."""
    list_display = ('quotation_number', 'client', 'total_amount', 'status', 'issue_date', 'valid_until')
    list_filter = ('status', 'issue_date')
    search_fields = ('quotation_number', 'client__name')
    readonly_fields = ('quotation_number', 'created_at', 'history')
    fieldsets = (
        (None, {'fields': ('quotation_number', 'client', 'status')}),
        ('Dates', {'fields': ('issue_date', 'valid_until')}),
        ('Amounts', {'fields': ('subtotal', 'tax_amount', 'total_amount')}),
        ('Notes & Feedback', {'fields': ('notes', 'client_feedback')}),
        ('System', {'fields': ('created_by', 'created_at', 'history')}),
    )
    raw_id_fields = ('client', 'created_by')


@admin.register(QuotationItem)
class QuotationItemAdmin(ModelAdmin):
    """Standalone admin for quotation line items."""
    list_display = ('quotation', 'description', 'quantity', 'unit_price', 'total')
    search_fields = ('description', 'quotation__quotation_number')
    raw_id_fields = ('quotation',)


@admin.register(Expense)
class ExpenseAdmin(ModelAdmin, SimpleHistoryAdmin):
    """Admin for expenses with approval workflow."""
    list_display = ('description', 'category', 'amount', 'date', 'status', 'recorded_by')
    list_filter = ('category', 'status', 'date')
    search_fields = ('description',)
    readonly_fields = ('created_at', 'history')
    fieldsets = (
        (None, {'fields': ('category', 'description', 'amount', 'date')}),
        ('Approval', {'fields': ('status', 'approved_by', 'approved_at')}),
        ('Receipt', {'fields': ('receipt',)}),
        ('System', {'fields': ('recorded_by', 'created_at', 'history')}),
    )
    raw_id_fields = ('recorded_by', 'approved_by')


@admin.register(Plan)
class PlanAdmin(ModelAdmin, SimpleHistoryAdmin):
    """Admin for subscription plans."""
    list_display = ('name', 'monthly_price', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)
    fieldsets = (
        (None, {'fields': ('name', 'description', 'monthly_price', 'is_active')}),
        ('Features', {'fields': ('features',), 'classes': ('collapse',)}),
    )


@admin.register(ClientSubscription)
class ClientSubscriptionAdmin(ModelAdmin, SimpleHistoryAdmin):
    """Admin for client subscriptions linking a client to a plan."""
    list_display = ('client', 'plan', 'status', 'start_date', 'current_period_end', 'cancel_at_period_end')
    list_filter = ('status', 'plan', 'cancel_at_period_end')
    search_fields = ('client__name', 'plan__name')
    readonly_fields = ('created_at', 'updated_at', 'history')
    fieldsets = (
        (None, {'fields': ('client', 'plan', 'status')}),
        ('Periods', {'fields': ('start_date', 'end_date', 'current_period_start', 'current_period_end', 'trial_end_date')}),
        ('Cancellation', {'fields': ('cancel_at_period_end',)}),
        ('System', {'fields': ('created_at', 'updated_at', 'history')}),
    )
    raw_id_fields = ('client',)