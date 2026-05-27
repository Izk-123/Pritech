from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import SiteConfig


@admin.register(SiteConfig)
class SiteConfigAdmin(ModelAdmin):
    list_display = ('company_name', 'email', 'phone')
    fieldsets = (
        (None, {'fields': ('company_name', 'tagline', 'logo')}),
        ('Contact', {'fields': ('email', 'phone', 'address', 'website')}),
        ('Financial', {'fields': ('vat_rate', 'currency', 'currency_symbol', 'bank_name', 'bank_account', 'mobile_money')}),
        ('Footer', {'fields': ('invoice_footer',)}),
    )