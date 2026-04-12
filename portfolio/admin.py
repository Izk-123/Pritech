from django.contrib import admin
from .models import PortfolioProject, Inquiry
admin.site.register(PortfolioProject)

@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'is_read', 'created_at')
    list_filter = ('is_read',)
