"""
Portfolio App Admin Configuration
================================
Complete admin for categories, projects, technologies, images, testimonials.
Includes inline management and CSV exports.
"""

import csv
from django.contrib import admin
from django.http import HttpResponse
from django import forms
from unfold.admin import ModelAdmin
from simple_history.admin import SimpleHistoryAdmin
from .models import (
    PortfolioCategory, PortfolioProject, PortfolioTechnology,
    PortfolioImage, Testimonial, Inquiry, NewsletterSubscriber, PortfolioSettings
)
from services.models import Service


# -----------------------------------------------------------------------------
# Inlines
# -----------------------------------------------------------------------------
class PortfolioImageInline(admin.TabularInline):
    model = PortfolioImage
    extra = 1
    fields = ("image", "caption", "order")
    ordering = ("order",)


class TestimonialInline(admin.TabularInline):
    model = Testimonial
    extra = 0
    fields = ("client_name", "client_position", "testimonial", "rating", "is_approved")
    show_change_link = True


class PortfolioProjectInlineForService(admin.TabularInline):
    """Used in Service admin to show related projects."""
    model = PortfolioProject.services.through
    extra = 0
    verbose_name = "Portfolio Project"
    verbose_name_plural = "Portfolio Projects using this service"
    fields = ("portfolio_project",)


# -----------------------------------------------------------------------------
# Portfolio Category Admin
# -----------------------------------------------------------------------------
@admin.register(PortfolioCategory)
class PortfolioCategoryAdmin(ModelAdmin, SimpleHistoryAdmin):
    list_display = ("name", "slug", "is_active", "order")
    list_filter = ("is_active",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("is_active", "order")
    readonly_fields = ("history",)


# -----------------------------------------------------------------------------
# Portfolio Technology Admin
# -----------------------------------------------------------------------------
@admin.register(PortfolioTechnology)
class PortfolioTechnologyAdmin(ModelAdmin, SimpleHistoryAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    readonly_fields = ("history",)


# -----------------------------------------------------------------------------
# Portfolio Project Admin
# -----------------------------------------------------------------------------
@admin.register(PortfolioProject)
class PortfolioProjectAdmin(ModelAdmin, SimpleHistoryAdmin):
    list_display = ("title", "client_name", "category", "status", "is_featured", "completion_date")
    list_filter = ("status", "is_featured", "category", "completion_date")
    search_fields = ("title", "client_name", "description", "full_description")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("services", "technologies")
    readonly_fields = ("created_at", "updated_at", "history")
    inlines = [PortfolioImageInline, TestimonialInline]
    fieldsets = (
        ("Basic Info", {"fields": ("title", "slug", "category", "client_name")}),
        ("Description", {"fields": ("description", "full_description")}),
        ("Media & Links", {"fields": ("featured_image", "project_url")}),
        ("Dates", {"fields": ("start_date", "completion_date")}),
        ("Relationships", {"fields": ("services", "technologies")}),
        ("Status", {"fields": ("status", "is_featured", "order")}),
        ("System", {"fields": ("created_at", "updated_at", "history"), "classes": ("collapse",)}),
    )


# -----------------------------------------------------------------------------
# Testimonial Admin (standalone)
# -----------------------------------------------------------------------------
@admin.register(Testimonial)
class TestimonialAdmin(ModelAdmin, SimpleHistoryAdmin):
    list_display = ("client_name", "project", "rating", "is_approved", "created_at")
    list_filter = ("is_approved", "rating", "created_at")
    search_fields = ("client_name", "testimonial")
    raw_id_fields = ("project",)
    readonly_fields = ("history",)


# -----------------------------------------------------------------------------
# Inquiry Admin
# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
# NewsletterSubscriber Admin
# -----------------------------------------------------------------------------
@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(ModelAdmin, SimpleHistoryAdmin):
    list_display = ("email", "subscribed_at", "is_active_display", "confirmed_at")
    list_filter = ("is_confirmed", "unsubscribed_at")
    search_fields = ("email",)
    readonly_fields = ("confirmation_token", "subscribed_at", "confirmed_at", "history")
    actions = ["mark_unsubscribed", "export_csv"]

    def get_queryset(self, request):
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


# -----------------------------------------------------------------------------
# PortfolioSettings Admin
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


# -----------------------------------------------------------------------------
# Extend ServiceAdmin from services app to show portfolio projects inline
# -----------------------------------------------------------------------------
try:
    from services.admin import ServiceAdmin as OriginalServiceAdmin

    class ExtendedServiceAdmin(OriginalServiceAdmin):
        inlines = list(OriginalServiceAdmin.inlines) + [PortfolioProjectInlineForService]

    if admin.site.is_registered(Service):
        admin.site.unregister(Service)
        admin.site.register(Service, ExtendedServiceAdmin)
except ImportError:
    pass