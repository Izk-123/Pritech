from unfold.admin import ModelAdmin
from unfold.decorators import action
from django.contrib import admin
from .models import PortfolioProject, Inquiry, NewsletterSubscriber, PortfolioSettings


@admin.register(PortfolioProject)
class PortfolioProjectAdmin(ModelAdmin):
    list_display = ('title', 'client_name', 'is_featured', 'order')
    list_filter = ('is_featured',)
    search_fields = ('title', 'client_name')
    list_editable = ('order', 'is_featured')
    readonly_fields = ('id',)


@admin.register(Inquiry)
class InquiryAdmin(ModelAdmin):
    list_display = ('name', 'email', 'subject', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('name', 'email', 'subject')
    actions = ['mark_as_read']

    @action(description="Mark selected as read")
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(ModelAdmin):
    list_display = ('email', 'subscribed_at')
    search_fields = ('email',)
    readonly_fields = ('subscribed_at',)


@admin.register(PortfolioSettings)
class PortfolioSettingsAdmin(ModelAdmin):
    fieldsets = (
        ("Hero Section", {"fields": ("hero_title", "hero_subtitle", "hero_image")}),
        ("About Section", {"fields": ("about_title", "about_text", "about_image")}),
        ("Achievements Counters", {"fields": ("projects_count", "satisfaction_percent", "support_hours", "years_experience")}),
        ("Social Links", {"fields": ("facebook_url", "twitter_url", "instagram_url", "linkedin_url", "whatsapp_number")}),
        ("SEO & Meta", {"fields": ("meta_description", "meta_keywords")}),
        ("Footer", {"fields": ("footer_copyright",)}),
    )