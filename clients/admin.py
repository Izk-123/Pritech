from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action
from .models import ClientOrganization, ClientContact


class ContactInline(TabularInline):
    model = ClientContact
    extra = 1
    fields = ('name', 'role', 'email', 'phone', 'is_primary')


@admin.register(ClientOrganization)
class ClientOrganizationAdmin(ModelAdmin):
    list_display = ('name', 'industry', 'status', 'email', 'phone', 'open_tickets', 'total_invoiced')
    list_filter = ('industry', 'status')
    search_fields = ('name', 'email', 'registration_number', 'tax_id')
    readonly_fields = ('created_at',)
    inlines = [ContactInline]
    actions = ['mark_active', 'mark_inactive', 'mark_lead']

    fieldsets = (
        (None, {'fields': ('name', 'industry', 'status')}),
        ('Contact & Registration', {'fields': ('email', 'phone', 'website', 'address', 'registration_number', 'tax_id')}),
        ('Notes & User Link', {'fields': ('notes', 'user'), 'classes': ('collapse',)}),
        ('System', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )

    @action(description="Mark selected as Active")
    def mark_active(self, request, queryset):
        queryset.update(status='active')

    @action(description="Mark selected as Inactive")
    def mark_inactive(self, request, queryset):
        queryset.update(status='inactive')

    @action(description="Mark selected as Lead")
    def mark_lead(self, request, queryset):
        queryset.update(status='lead')


@admin.register(ClientContact)
class ClientContactAdmin(ModelAdmin):
    list_display = ('name', 'client', 'role', 'email', 'phone', 'is_primary')
    list_filter = ('client', 'is_primary')
    search_fields = ('name', 'email', 'role')
    readonly_fields = ('id',)