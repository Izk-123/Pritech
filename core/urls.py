# core/urls.py
from django.urls import path
from .views import DashboardView, dashboard_stats_partial, AuditLogView, PageVisitView

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('stats-partial/', dashboard_stats_partial, name='dashboard_stats_partial'),
    path('audit/', AuditLogView.as_view(), name='audit_log'),
    path('visits/', PageVisitView.as_view(), name='page_visits'),
]