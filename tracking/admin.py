from django.contrib import admin
from .models import UserActivity, PageVisit

@admin.register(PageVisit)
class PageVisitAdmin(admin.ModelAdmin):
    list_display = ('page_url', 'user', 'ip_address', 'timestamp')
    list_filter = ('timestamp',)

admin.site.register(UserActivity)
