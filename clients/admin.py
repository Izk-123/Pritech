# clients/admin.py
from unfold.admin import ModelAdmin
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import ClientOrganization, ClientContact


class ContactInline(admin.TabularInline):
    model = ClientContact
    extra = 1
    fields = ('name', 'role', 'email', 'phone', 'is_primary')


@admin.register(ClientOrganization)
class ClientOrganizationAdmin(ModelAdmin, SimpleHistoryAdmin):
    list_display = ('name', 'industry', 'status', 'email', 'phone', 'open_tickets', 'total_invoiced')
    list_filter = ('industry', 'status', 'created_at')
    search_fields = ('name', 'email', 'phone', 'registration_number', 'tax_id')
    readonly_fields = ('created_at', 'history')
    inlines = [ContactInline]
    actions = ['mark_active', 'mark_inactive', 'mark_lead']
    fieldsets = (
        (None, {'fields': ('name', 'industry', 'status', 'assigned_to')}),
        ('Contact & Registration', {'fields': ('email', 'phone', 'website', 'address', 'registration_number', 'tax_id')}),
        ('Notes & User Link', {'fields': ('notes', 'user', 'logo'), 'classes': ('collapse',)}),
        ('System', {'fields': ('created_at', 'history'), 'classes': ('collapse',)}),
    )

    def mark_active(self, request, queryset):
        queryset.update(status='active')
    mark_active.short_description = "Mark selected as Active"

    def mark_inactive(self, request, queryset):
        queryset.update(status='inactive')
    mark_inactive.short_description = "Mark selected as Inactive"

    def mark_lead(self, request, queryset):
        queryset.update(status='lead')
    mark_lead.short_description = "Mark selected as Lead"


@admin.register(ClientContact)
class ClientContactAdmin(ModelAdmin, SimpleHistoryAdmin):
    list_display = ('name', 'client', 'role', 'email', 'phone', 'is_primary')
    list_filter = ('client', 'is_primary')
    search_fields = ('name', 'email', 'role')
    readonly_fields = ('history',)