# core/urls.py
from django.urls import path
from core.admin_views import admin_inline_ticket_status, admin_live_ticket_search
from core.htmx_views import ticket_search, update_ticket_status
from .views import (
    DashboardView, core_dashboard_stats_partial,
    AuditLogView, PageVisitView, global_search,
    SiteConfigurationView, AnnouncementListView,
    AnnouncementCreateView, AnnouncementUpdateView, announcement_delete,
)

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('stats-partial/', core_dashboard_stats_partial, name='core_dashboard_stats_partial'),

    # Site configuration (Super Admin / Admin)
    path('settings/', SiteConfigurationView.as_view(), name='site_configuration'),

    # Announcements (Admin)
    path('announcements/', AnnouncementListView.as_view(), name='announcement_list'),
    path('announcements/new/', AnnouncementCreateView.as_view(), name='announcement_create'),
    path('announcements/<int:pk>/edit/', AnnouncementUpdateView.as_view(), name='announcement_update'),
    path('announcements/<int:pk>/delete/', announcement_delete, name='announcement_delete'),

    # Audit log & page visits
    path('audit/', AuditLogView.as_view(), name='audit_log'),
    path('visits/', PageVisitView.as_view(), name='page_visits'),

    # Global search
    path('search/', global_search, name='global_search'),

    # HTMX ticket search / inline status (staff)
    path('htmx/ticket-search/', ticket_search, name='htmx_ticket_search'),
    path('htmx/ticket-status/<int:ticket_id>/', update_ticket_status, name='htmx_update_ticket_status'),

    # Admin (Unfold) live search / inline status
    path('admin/live-search/', admin_live_ticket_search, name='admin_live_ticket_search'),
    path('admin/ticket-status/<int:ticket_id>/', admin_inline_ticket_status, name='admin_inline_ticket_status'),
]