# services/urls.py
from django.urls import path
from .views import (
    # Staff service management
    ServiceListView, ServiceDetailView, ServiceCreateView, ServiceUpdateView, ServiceDeleteView,
    ServiceBulkActionView, ServiceExportCSVView, service_toggle_status,
    # Staff category management
    ServiceCategoryListView, ServiceCategoryCreateView, ServiceCategoryUpdateView,
    # Staff package management
    ServicePackageListView, ServicePackageCreateView, ServicePackageUpdateView, ServicePackageDeleteView,
    # Client catalog & quote requests
    ClientServiceCatalogView, RequestServiceQuoteView, RequestPackageQuoteView,
    # Service request workflow
    CreateServiceRequestView, ClientServiceRequestListView,
    StaffServiceRequestListView, ApproveServiceRequestView, RejectServiceRequestView,
    AssignTechnicianView, TechnicianAssignmentListView, CompleteAssignmentView,
    # Analytics
    ServiceAnalyticsView,
)

urlpatterns = [
    # ──────────────────────────────────────────────────────────────────────────
    # Staff‑only: Service management
    # ──────────────────────────────────────────────────────────────────────────
    path('', ServiceListView.as_view(), name='service_list'),
    path('<int:pk>/', ServiceDetailView.as_view(), name='service_detail'),
    path('new/', ServiceCreateView.as_view(), name='service_create'),
    path('<int:pk>/edit/', ServiceUpdateView.as_view(), name='service_update'),
    path('<int:pk>/delete/', ServiceDeleteView.as_view(), name='service_delete'),
    path('bulk-action/', ServiceBulkActionView.as_view(), name='service_bulk_action'),
    path('export/', ServiceExportCSVView.as_view(), name='service_export_csv'),
    # HTMX endpoint for inline status toggle
    path('service_toggle_status/<int:pk>/', service_toggle_status, name='service_toggle_status'),

    # ──────────────────────────────────────────────────────────────────────────
    # Staff‑only: Categories (restricted)
    # ──────────────────────────────────────────────────────────────────────────
    path('categories/', ServiceCategoryListView.as_view(), name='service_category_list'),
    path('categories/new/', ServiceCategoryCreateView.as_view(), name='service_category_create'),
    path('categories/<int:pk>/edit/', ServiceCategoryUpdateView.as_view(), name='service_category_update'),

    # ──────────────────────────────────────────────────────────────────────────
    # Staff‑only: Packages (restricted)
    # ──────────────────────────────────────────────────────────────────────────
    path('packages/', ServicePackageListView.as_view(), name='service_package_list'),
    path('packages/new/', ServicePackageCreateView.as_view(), name='service_package_create'),
    path('packages/<int:pk>/edit/', ServicePackageUpdateView.as_view(), name='service_package_update'),
    path('packages/<int:pk>/delete/', ServicePackageDeleteView.as_view(), name='service_package_delete'),

    # ──────────────────────────────────────────────────────────────────────────
    # Client‑facing catalog & quote requests (rate‑limited)
    # ──────────────────────────────────────────────────────────────────────────
    path('catalog/', ClientServiceCatalogView.as_view(), name='client_service_catalog'),
    path('request-quote/<int:service_pk>/', RequestServiceQuoteView.as_view(), name='request_service_quote'),
    path('request-package-quote/<int:package_pk>/', RequestPackageQuoteView.as_view(), name='request_package_quote'),

    # ──────────────────────────────────────────────────────────────────────────
    # Service Request Workflow (Client)
    # ──────────────────────────────────────────────────────────────────────────
    path('requests/new/', CreateServiceRequestView.as_view(), name='create_service_request'),
    path('my-requests/', ClientServiceRequestListView.as_view(), name='client_service_requests'),

    # ──────────────────────────────────────────────────────────────────────────
    # Service Request Workflow (Staff)
    # ──────────────────────────────────────────────────────────────────────────
    path('staff/requests/', StaffServiceRequestListView.as_view(), name='staff_service_request_list'),
    path('staff/requests/<int:pk>/approve/', ApproveServiceRequestView.as_view(), name='approve_service_request'),
    path('staff/requests/<int:pk>/reject/', RejectServiceRequestView.as_view(), name='reject_service_request'),
    path('staff/requests/<int:pk>/assign/', AssignTechnicianView.as_view(), name='assign_technician'),

    # ──────────────────────────────────────────────────────────────────────────
    # Technician assignments
    # ──────────────────────────────────────────────────────────────────────────
    path('my-assignments/', TechnicianAssignmentListView.as_view(), name='technician_assignments'),
    path('assignments/<int:pk>/complete/', CompleteAssignmentView.as_view(), name='complete_assignment'),

    # ──────────────────────────────────────────────────────────────────────────
    # Analytics
    # ──────────────────────────────────────────────────────────────────────────
    path('analytics/', ServiceAnalyticsView.as_view(), name='service_analytics'),
]