from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import ServiceCategory, Service, ServicePackage


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(ModelAdmin):
    list_display = ('name', 'icon')
    search_fields = ('name',)
    readonly_fields = ('id',)


@admin.register(Service)
class ServiceAdmin(ModelAdmin):
    list_display = ('name', 'category', 'base_price', 'unit', 'billing_type', 'is_active')
    list_filter = ('category', 'billing_type', 'is_active')
    search_fields = ('name',)
    list_editable = ('is_active',)


@admin.register(ServicePackage)
class ServicePackageAdmin(ModelAdmin):
    list_display = ('name', 'monthly_price', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    filter_horizontal = ('services',)