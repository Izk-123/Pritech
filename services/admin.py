from django.contrib import admin
from .models import Service, ServiceCategory, ServicePackage


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'description')
    search_fields = ('name',)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'base_price', 'unit', 'billing_type', 'is_active')
    list_filter = ('category', 'billing_type', 'is_active')
    search_fields = ('name', 'description')


@admin.register(ServicePackage)
class ServicePackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'monthly_price', 'is_active')
    filter_horizontal = ('services',)
    search_fields = ('name', 'description')