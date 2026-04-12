from django.urls import path
from django.views.generic import RedirectView
from .views import DashboardView, AuditLogView, PageVisitView

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('audit/', AuditLogView.as_view(), name='audit_log'),
    path('visits/', PageVisitView.as_view(), name='page_visits'),
]
