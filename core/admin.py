# core/admin.py
from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import (
    SiteConfig, CompanyBranch, DashboardWidget,
    Announcement, ActivityFeed, SystemNotification
)


@admin.register(SiteConfig)
class SiteConfigAdmin(ModelAdmin):
    list_display = ('company_name', 'email', 'phone')
    fieldsets = (
        (None, {'fields': ('company_name', 'tagline', 'logo', 'maintenance_mode')}),
        ('Contact', {'fields': ('email', 'phone', 'address', 'website')}),
        ('Financial', {'fields': ('vat_rate', 'currency', 'currency_symbol', 'bank_name', 'bank_account', 'mobile_money')}),
        ('Footer', {'fields': ('invoice_footer',)}),
    )


@admin.register(CompanyBranch)
class CompanyBranchAdmin(ModelAdmin):
    list_display = ('name', 'phone', 'email', 'is_main')
    list_filter = ('is_main',)
    search_fields = ('name',)


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'order')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    filter_horizontal = ('roles',)


@admin.register(Announcement)
class AnnouncementAdmin(ModelAdmin):
    list_display = ('title', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active', 'start_date', 'end_date')
    search_fields = ('title',)
    date_hierarchy = 'start_date'


@admin.register(ActivityFeed)
class ActivityFeedAdmin(ModelAdmin):
    list_display = ('action', 'module', 'user', 'timestamp')
    list_filter = ('module', 'timestamp')
    search_fields = ('action',)
    readonly_fields = ('user', 'action', 'module', 'object_id', 'timestamp')
    list_select_related = ('user',)


@admin.register(SystemNotification)
class SystemNotificationAdmin(ModelAdmin):
    list_display = ('title', 'user', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('title', 'user__email')
    list_select_related = ('user',)
    raw_id_fields = ('user',)