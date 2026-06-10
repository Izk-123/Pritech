# services/admin.py
"""
Services App Admin Configuration
-------------------------------
Registers ServiceCategory, Service, and ServicePackage with Unfold's ModelAdmin.
Includes simple_history for audit logging.
"""

from unfold.admin import ModelAdmin
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import ServiceCategory, Service, ServicePackage


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(ModelAdmin, SimpleHistoryAdmin):
    """Admin for service categories (no created_at field)."""
    list_display = ('name', 'icon', 'services_count')
    search_fields = ('name',)
    # Removed 'created_at' from list_filter because the field doesn't exist
    fieldsets = (
        (None, {'fields': ('name', 'icon', 'description')}),
        ('System', {'fields': ('history',), 'classes': ('collapse',)}),
    )
    readonly_fields = ('history',)

    def services_count(self, obj):
        return obj.services.count()
    services_count.short_description = 'Services'


@admin.register(Service)
class ServiceAdmin(ModelAdmin, SimpleHistoryAdmin):
    """Admin for individual services."""
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


@admin.register(ServicePackage)
class ServicePackageAdmin(ModelAdmin, SimpleHistoryAdmin):
    """Admin for service packages."""
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