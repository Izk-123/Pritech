"""
Portfolio App Admin Configuration
================================
- Registered models with Unfold + SimpleHistoryAdmin.
- CSV export actions for Inquiry and NewsletterSubscriber.
- Soft-delete filtering for subscribers.
- Inline validation for image sizes.
"""

import csv
from django.contrib import admin
from django.http import HttpResponse
from django import forms
from unfold.admin import ModelAdmin
from simple_history.admin import SimpleHistoryAdmin
from .models import PortfolioProject, Inquiry, NewsletterSubscriber, PortfolioSettings


# -----------------------------------------------------------------------------
# Custom form for PortfolioSettings to validate image size at admin level
# -----------------------------------------------------------------------------
class PortfolioSettingsForm(forms.ModelForm):
    class Meta:
        model = PortfolioSettings
        fields = "__all__"

    def clean_hero_image(self):
        image = self.cleaned_data.get("hero_image")
        if image and image.size > 2 * 1024 * 1024:
            raise forms.ValidationError("Hero image must be ≤ 2MB.")
        return image

    def clean_about_image(self):
        image = self.cleaned_data.get("about_image")
        if image and image.size > 2 * 1024 * 1024:
            raise forms.ValidationError("About image must be ≤ 2MB.")
        return image


# -----------------------------------------------------------------------------
# Admin classes
# -----------------------------------------------------------------------------

@admin.register(PortfolioProject)
class PortfolioProjectAdmin(ModelAdmin, SimpleHistoryAdmin):
    list_display = ("title", "client_name", "is_featured", "order")
    list_filter = ("is_featured",)
    search_fields = ("title", "client_name")
    list_editable = ("order", "is_featured")
    readonly_fields = ("id", "history")
    fieldsets = (
        (None, {"fields": ("title", "description", "image")}),
        ("Details", {"fields": ("client_name", "technologies", "is_featured", "order")}),
        ("Audit", {"fields": ("history",), "classes": ("collapse",)}),
    )


@admin.register(Inquiry)
class InquiryAdmin(ModelAdmin, SimpleHistoryAdmin):
    list_display = ("name", "email", "subject", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("name", "email", "subject")
    readonly_fields = ("history",)
    actions = ["mark_as_read", "export_csv"]

    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
    mark_as_read.short_description = "Mark selected as read"

    def export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="inquiries.csv"'
        writer = csv.writer(response)
        writer.writerow(["Name", "Email", "Phone", "Subject", "Message", "Created At", "Is Read"])
        for obj in queryset:
            writer.writerow([
                obj.name, obj.email, obj.phone, obj.subject,
                obj.message, obj.created_at.strftime("%Y-%m-%d %H:%M"),
                "Yes" if obj.is_read else "No"
            ])
        return response
    export_csv.short_description = "Export selected to CSV"


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(ModelAdmin, SimpleHistoryAdmin):
    list_display = ("email", "subscribed_at", "is_active_display", "confirmed_at")
    list_filter = ("is_confirmed", "unsubscribed_at")
    search_fields = ("email",)
    readonly_fields = ("confirmation_token", "subscribed_at", "confirmed_at", "history")
    actions = ["mark_unsubscribed", "export_csv"]

    def get_queryset(self, request):
        """Show only active (non-unsubscribed) subscribers by default."""
        return super().get_queryset(request).filter(unsubscribed_at__isnull=True)

    def is_active_display(self, obj):
        return obj.is_active()
    is_active_display.boolean = True
    is_active_display.short_description = "Active"

    def mark_unsubscribed(self, request, queryset):
        from django.utils import timezone
        queryset.update(unsubscribed_at=timezone.now())
    mark_unsubscribed.short_description = "Unsubscribe selected"

    def export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="subscribers.csv"'
        writer = csv.writer(response)
        writer.writerow(["Email", "Subscribed At", "Confirmed At", "Active", "IP Address"])
        for obj in queryset:
            writer.writerow([
                obj.email,
                obj.subscribed_at.strftime("%Y-%m-%d %H:%M"),
                obj.confirmed_at.strftime("%Y-%m-%d %H:%M") if obj.confirmed_at else "",
                "Yes" if obj.is_active() else "No",
                obj.ip_address or "",
            ])
        return response
    export_csv.short_description = "Export selected to CSV"


@admin.register(PortfolioSettings)
class PortfolioSettingsAdmin(ModelAdmin, SimpleHistoryAdmin):
    form = PortfolioSettingsForm
    fieldsets = (
        ("Hero Section", {"fields": ("hero_title", "hero_subtitle", "hero_image")}),
        ("About Section", {"fields": ("about_title", "about_text", "about_image")}),
        ("Achievements Counters", {"fields": ("projects_count", "satisfaction_percent", "support_hours", "years_experience")}),
        ("Social Links", {"fields": ("facebook_url", "twitter_url", "instagram_url", "linkedin_url", "whatsapp_number")}),
        ("SEO & Meta", {"fields": ("meta_description", "meta_keywords")}),
        ("Footer", {"fields": ("footer_copyright",)}),
        ("Audit", {"fields": ("history",), "classes": ("collapse",)}),
    )
    readonly_fields = ("history",)