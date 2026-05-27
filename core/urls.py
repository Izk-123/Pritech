# core/urls.py
from django.urls import path

from core.admin_views import admin_inline_ticket_status, admin_live_ticket_search
from core.htmx_views import ticket_search, update_ticket_status
from .views import DashboardView, dashboard_stats_partial, AuditLogView, PageVisitView, htmx_dashboard, inline_ticket_status, live_ticket_search, live_ticket_search

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('stats-partial/', dashboard_stats_partial, name='dashboard_stats_partial'),
    path('audit/', AuditLogView.as_view(), name='audit_log'),
    path('visits/', PageVisitView.as_view(), name='page_visits'),
    path('htmx-dashboard/', htmx_dashboard, name='htmx_dashboard'),
    path('live-search/', live_ticket_search, name='live_ticket_search'),
    path('inline-status/<int:ticket_id>/', inline_ticket_status, name='inline_ticket_status'),
    path('admin/live-search/', admin_live_ticket_search, name='admin_live_ticket_search'),
    path('admin/ticket-status/<int:ticket_id>/', admin_inline_ticket_status, name='admin_inline_ticket_status'),
    path('htmx/ticket-search/', ticket_search, name='htmx_ticket_search'),
    path('htmx/ticket-status/<int:ticket_id>/', update_ticket_status, name='htmx_update_ticket_status'),
]

