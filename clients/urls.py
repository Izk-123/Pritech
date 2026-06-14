# clients/urls.py
from django.urls import path
from .views import (
    ClientListView, ClientCreateView, ClientDetailView, ClientUpdateView, ClientDeleteView,
    ClientBulkActionView, ClientExportCSVView,
    ClientContactListView, ClientContactCreateView, ClientContactUpdateView, ClientContactDeleteView,
)

urlpatterns = [
    # Main client management
    path('', ClientListView.as_view(), name='client_list'),
    path('new/', ClientCreateView.as_view(), name='client_create'),
    path('<uuid:pk>/', ClientDetailView.as_view(), name='client_detail'),
    path('<uuid:pk>/edit/', ClientUpdateView.as_view(), name='client_update'),
    path('<uuid:pk>/delete/', ClientDeleteView.as_view(), name='client_delete'),

    # Bulk actions & export
    path('bulk-action/', ClientBulkActionView.as_view(), name='client_bulk_action'),
    path('export/', ClientExportCSVView.as_view(), name='client_export_csv'),

    # Client‑facing contact management (for clients)
    path('contacts/', ClientContactListView.as_view(), name='client_contact_list'),
    path('contacts/new/', ClientContactCreateView.as_view(), name='client_contact_create'),
    path('contacts/<int:pk>/edit/', ClientContactUpdateView.as_view(), name='client_contact_update'),
    path('contacts/<int:pk>/delete/', ClientContactDeleteView.as_view(), name='client_contact_delete'),
]