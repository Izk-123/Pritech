"""
Tracking App URL Configuration
==============================
- Opt-out, GDPR export/delete, and staff dashboard.
"""

from django.urls import path
from .views import (
    tracking_opt_out,
    tracking_data_export,
    tracking_data_delete,
    tracking_dashboard,
)

urlpatterns = [
    path("opt-out/", tracking_opt_out, name="tracking_opt_out"),
    path("export/", tracking_data_export, name="tracking_data_export"),
    path("delete/", tracking_data_delete, name="tracking_data_delete"),
    path("dashboard/", tracking_dashboard, name="tracking_dashboard"),
]