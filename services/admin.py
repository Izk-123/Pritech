from django.contrib import admin
from .models import Service, ServiceCategory
admin.site.register(ServiceCategory)

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'base_price', 'unit', 'is_active')
    list_filter = ('category', 'is_active')
