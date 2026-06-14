# core/models.py
"""
Core App Models
---------------
Site Configuration, Company Branches, Dashboard Widgets,
Announcements, Activity Feed, and System Notifications.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class SiteConfig(models.Model):
    """Company‑wide settings and branding."""
    company_name = models.CharField(max_length=200, default='Pritech ICT Solutions')
    tagline = models.CharField(max_length=300, blank=True)
    logo = models.ImageField(upload_to='logo/', null=True, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.175)
    currency = models.CharField(max_length=10, default='Malaŵian Kwacha')
    currency_symbol = models.CharField(max_length=5, default='MWK')
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account = models.CharField(max_length=50, blank=True)
    mobile_money = models.CharField(max_length=50, blank=True)
    invoice_footer = models.TextField(blank=True)

    # NEW: Maintenance mode
    maintenance_mode = models.BooleanField(
        default=False,
        help_text="If enabled, only staff can access the site (non‑staff see maintenance page)."
    )

    class Meta:
        verbose_name = 'Site Configuration'

    def __str__(self):
        return self.company_name

    @classmethod
    def get(cls):
        """Get or create the singleton configuration."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class CompanyBranch(models.Model):
    """For future multi‑branch support."""
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    is_main = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class DashboardWidget(models.Model):
    """Configurable dashboard widget for role‑based dashboards."""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True, help_text="Identifier used in template logic")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    roles = models.ManyToManyField('accounts.Role', blank=True, help_text="Roles that can see this widget (empty = all)")

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Announcement(models.Model):
    """System‑wide announcements shown on the dashboard."""
    title = models.CharField(max_length=200)
    message = models.TextField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def is_current(self):
        """Check if announcement is currently visible."""
        now = timezone.now()
        return self.is_active and self.start_date <= now <= self.end_date

    def __str__(self):
        return self.title


class ActivityFeed(models.Model):
    """Central activity feed across all apps."""
    MODULE_CHOICES = (
        ('tickets', 'Tickets'),
        ('finance', 'Finance'),
        ('clients', 'Clients'),
        ('accounts', 'Accounts'),
        ('services', 'Services'),
        ('system', 'System'),
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255, help_text="e.g., Created invoice #INV-001")
    module = models.CharField(max_length=50, choices=MODULE_CHOICES)
    object_id = models.CharField(max_length=100, blank=True, help_text="Identifier of related object")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} - {self.timestamp}"


class SystemNotification(models.Model):
    """In‑app notifications for individual users."""
    NOTIFICATION_TYPES = (
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('success', 'Success'),
        ('error', 'Error'),
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='info')
    is_read = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.user.email}"