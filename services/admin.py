# services/admin.py
"""
Services App Admin Configuration
-------------------------------
Registers all service‑related models with Unfold's ModelAdmin and simple_history.
Includes:
- ServiceCategory, Service, ServicePackage
- ServiceRequest, ClientService, ServiceAssignment (full lifecycle)

All admins support historical audit logs and modern UI via Unfold.
"""

from unfold.admin import ModelAdmin
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from django.db.models import Count

from .models import (
    ServiceCategory, Service, ServicePackage,
    ServiceRequest, ClientService, ServiceAssignment
)


# -----------------------------------------------------------------------------
# Service Category Admin
# -----------------------------------------------------------------------------
@admin.register(ServiceCategory)
class ServiceCategoryAdmin(ModelAdmin, SimpleHistoryAdmin):
    """Admin for service categories with annotated service count."""
    list_display = ('name', 'icon', 'services_count')
    search_fields = ('name',)
    fieldsets = (
        (None, {'fields': ('name', 'icon', 'description')}),
        ('System', {'fields': ('history',), 'classes': ('collapse',)}),
    )
    readonly_fields = ('history',)

    def get_queryset(self, request):
        """Annotate with services count to avoid N+1 queries."""
        return super().get_queryset(request).annotate(services_count=Count('services'))

    def services_count(self, obj):
        return obj.services_count
    services_count.short_description = 'Services'
    services_count.admin_order_field = 'services_count'


# -----------------------------------------------------------------------------
# Individual Service Admin
# -----------------------------------------------------------------------------
@admin.register(Service)
class ServiceAdmin(ModelAdmin, SimpleHistoryAdmin):
    """Admin for individual services with slug prepopulation."""
    list_display = ('name', 'category', 'base_price', 'unit', 'billing_type', 'is_active', 'created_at')
    list_filter = ('category', 'billing_type', 'is_active', 'created_at')
    search_fields = ('name', 'category__name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'category', 'description')}),
        ('Pricing & Billing', {'fields': ('base_price', 'unit', 'billing_type')}),
        ('Status', {'fields': ('is_active',)}),
        ('System', {'fields': ('created_at', 'history'), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at', 'history')


# -----------------------------------------------------------------------------
# Service Package Admin
# -----------------------------------------------------------------------------
@admin.register(ServicePackage)
class ServicePackageAdmin(ModelAdmin, SimpleHistoryAdmin):
    """Admin for service packages with horizontal filter for services."""
    list_display = ('name', 'monthly_price', 'is_active', 'services_count', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name',)
    filter_horizontal = ('services',)
    fieldsets = (
        (None, {'fields': ('name', 'description', 'services')}),
        ('Pricing', {'fields': ('monthly_price',)}),
        ('Status', {'fields': ('is_active',)}),
        ('System', {'fields': ('created_at', 'history'), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at', 'history')

    def services_count(self, obj):
        return obj.services.count()
    services_count.short_description = 'Services'


# -----------------------------------------------------------------------------
# Service Request Admin (client demand workflow)
# -----------------------------------------------------------------------------
@admin.register(ServiceRequest)
class ServiceRequestAdmin(ModelAdmin, SimpleHistoryAdmin):
    """Admin for client service requests – supports approval workflow."""
    list_display = ('id', 'client', 'service', 'status', 'requested_at', 'reviewed_by')
    list_filter = ('status', 'requested_at', 'client')
    search_fields = ('client__name', 'service__name', 'description')
    raw_id_fields = ('client', 'service', 'reviewed_by', 'quotation')
    readonly_fields = ('requested_at', 'reviewed_at', 'history')
    fieldsets = (
        (None, {'fields': ('client', 'service', 'description', 'status')}),
        ('Review', {'fields': ('reviewed_by', 'reviewed_at', 'rejection_reason')}),
        ('Quotation', {'fields': ('quotation',)}),
        ('System', {'fields': ('requested_at', 'history'), 'classes': ('collapse',)}),
    )


# -----------------------------------------------------------------------------
# Client Service Admin (purchased services)
# -----------------------------------------------------------------------------
@admin.register(ClientService)
class ClientServiceAdmin(ModelAdmin, SimpleHistoryAdmin):
    """Admin for services purchased by clients (active/historical)."""
    list_display = ('client', 'service', 'start_date', 'end_date', 'status', 'created_at')
    list_filter = ('status', 'start_date', 'client')
    search_fields = ('client__name', 'service__name')
    raw_id_fields = ('client', 'service', 'invoice')
    readonly_fields = ('created_at', 'history')
    fieldsets = (
        (None, {'fields': ('client', 'service', 'status')}),
        ('Period', {'fields': ('start_date', 'end_date')}),
        ('Invoice', {'fields': ('invoice',)}),
        ('System', {'fields': ('created_at', 'history'), 'classes': ('collapse',)}),
    )


# -----------------------------------------------------------------------------
# Service Assignment Admin (technician assignments)
# -----------------------------------------------------------------------------
@admin.register(ServiceAssignment)
class ServiceAssignmentAdmin(ModelAdmin, SimpleHistoryAdmin):
    """Admin for technician assignments to service requests."""
    list_display = ('service_request', 'technician', 'assigned_at', 'completed_at')
    list_filter = ('assigned_at', 'completed_at')
    search_fields = ('service_request__client__name', 'technician__email')
    raw_id_fields = ('service_request', 'technician')
    readonly_fields = ('assigned_at', 'history')
    fieldsets = (
        (None, {'fields': ('service_request', 'technician', 'notes')}),
        ('Completion', {'fields': ('completed_at',)}),
        ('System', {'fields': ('assigned_at', 'history'), 'classes': ('collapse',)}),
    )