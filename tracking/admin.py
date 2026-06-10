"""
Tracking App Admin Configuration
================================
Restricted access: only superusers or users with explicit permission.
Includes custom actions to delete old records and export CSV.
"""

from django.contrib import admin
from django.http import HttpResponse
from unfold.admin import ModelAdmin
from simple_history.admin import SimpleHistoryAdmin
from .models import TrackingConsent, PageVisit, UserActivity
import csv
from django.utils import timezone
from datetime import timedelta


@admin.register(TrackingConsent)
class TrackingConsentAdmin(ModelAdmin, SimpleHistoryAdmin):
    list_display = ("user", "session_key", "consent_given", "consented_at", "withdrawn_at")
    list_filter = ("consent_given", "consented_at")
    search_fields = ("user__email", "session_key")
    readonly_fields = ("history",)

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(PageVisit)
class PageVisitAdmin(ModelAdmin, SimpleHistoryAdmin):
    list_display = ("page_url", "user", "timestamp", "consent_given")
    list_filter = ("timestamp", "consent_given")
    search_fields = ("page_url", "user__email")
    readonly_fields = ("history",)
    date_hierarchy = "timestamp"
    actions = ["export_csv", "delete_old_records"]

    def has_view_permission(self, request, obj=None):
        # Only superusers or users with custom permission
        return request.user.is_superuser or request.user.has_perm("tracking.view_pagevisit")

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="page_visits.csv"'
        writer = csv.writer(response)
        writer.writerow(["Page URL", "User", "Timestamp", "IP Hash", "User Agent", "Consent Given"])
        for obj in queryset:
            writer.writerow([
                obj.page_url,
                obj.user.email if obj.user else "Anonymous",
                obj.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                obj.ip_hash,
                obj.user_agent[:100],
                "Yes" if obj.consent_given else "No",
            ])
        return response
    export_csv.short_description = "Export selected to CSV"

    def delete_old_records(self, request, queryset):
        cutoff = timezone.now() - timedelta(days=90)
        deleted, _ = queryset.filter(timestamp__lt=cutoff).delete()
        self.message_user(request, f"Deleted {deleted} records older than 90 days.")
    delete_old_records.short_description = "Delete selected records older than 90 days"


@admin.register(UserActivity)
class UserActivityAdmin(ModelAdmin, SimpleHistoryAdmin):
    list_display = ("user", "action", "timestamp")
    list_filter = ("timestamp",)
    search_fields = ("user__email", "action")
    readonly_fields = ("history",)
    date_hierarchy = "timestamp"
    actions = ["export_csv"]

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.has_perm("tracking.view_useractivity")

    def export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="user_activities.csv"'
        writer = csv.writer(response)
        writer.writerow(["User", "Action", "Timestamp", "IP Hash", "User Agent"])
        for obj in queryset:
            writer.writerow([
                obj.user.email if obj.user else "Anonymous",
                obj.action,
                obj.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                obj.ip_hash,
                obj.user_agent[:100],
            ])
        return response
    export_csv.short_description = "Export selected to CSV"