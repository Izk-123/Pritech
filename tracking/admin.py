from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import UserActivity, PageVisit


@admin.register(PageVisit)
class PageVisitAdmin(ModelAdmin):
    list_display = ('page_url', 'user', 'ip_address', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('page_url', 'user__email')
    readonly_fields = ('user', 'page_url', 'ip_address', 'user_agent', 'timestamp')


@admin.register(UserActivity)
class UserActivityAdmin(ModelAdmin):
    list_display = ('user', 'action', 'ip_address', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('user__email', 'action')
    readonly_fields = ('user', 'action', 'ip_address', 'user_agent', 'timestamp')