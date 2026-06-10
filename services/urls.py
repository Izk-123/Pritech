# services/urls.py
"""
Services App URL Configuration
-------------------------------
Handles service catalogue, categories, packages, client catalog,
bulk actions, CSV export, and quote requests.
"""

from django.urls import path
from .views import (
    # Staff service management
    ServiceListView, ServiceCreateView, ServiceUpdateView, ServiceDeleteView,
    ServiceBulkActionView, ServiceExportCSVView,
    # Staff category management
    ServiceCategoryListView, ServiceCategoryCreateView, ServiceCategoryUpdateView,
    # Staff package management
    ServicePackageListView, ServicePackageCreateView, ServicePackageUpdateView, ServicePackageDeleteView,
    # Client catalog & quote requests
    ClientServiceCatalogView, RequestServiceQuoteView, RequestPackageQuoteView,
)

urlpatterns = [
    # ──────────────────────────────────────────────────────────────────────────
    # Staff‑only: Service management (with bulk actions and export)
    # ──────────────────────────────────────────────────────────────────────────
    path('', ServiceListView.as_view(), name='service_list'),
    path('new/', ServiceCreateView.as_view(), name='service_create'),
    path('<int:pk>/edit/', ServiceUpdateView.as_view(), name='service_update'),
    path('<int:pk>/delete/', ServiceDeleteView.as_view(), name='service_delete'),
    path('bulk-action/', ServiceBulkActionView.as_view(), name='service_bulk_action'),
    path('export/', ServiceExportCSVView.as_view(), name='service_export_csv'),

    # ──────────────────────────────────────────────────────────────────────────
    # Staff‑only: Categories
    # ──────────────────────────────────────────────────────────────────────────
    path('categories/', ServiceCategoryListView.as_view(), name='service_category_list'),
    path('categories/new/', ServiceCategoryCreateView.as_view(), name='service_category_create'),
    path('categories/<int:pk>/edit/', ServiceCategoryUpdateView.as_view(), name='service_category_update'),

    # ──────────────────────────────────────────────────────────────────────────
    # Staff‑only: Packages
    # ──────────────────────────────────────────────────────────────────────────
    path('packages/', ServicePackageListView.as_view(), name='service_package_list'),
    path('packages/new/', ServicePackageCreateView.as_view(), name='service_package_create'),
    path('packages/<int:pk>/edit/', ServicePackageUpdateView.as_view(), name='service_package_update'),
    path('packages/<int:pk>/delete/', ServicePackageDeleteView.as_view(), name='service_package_delete'),

    # ──────────────────────────────────────────────────────────────────────────
    # Client‑facing catalog & quote requests
    # ──────────────────────────────────────────────────────────────────────────
    path('catalog/', ClientServiceCatalogView.as_view(), name='client_service_catalog'),
    path('request-quote/<int:service_pk>/', RequestServiceQuoteView.as_view(), name='request_service_quote'),
    path('request-package-quote/<int:package_pk>/', RequestPackageQuoteView.as_view(), name='request_package_quote'),
]