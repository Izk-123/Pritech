# finance/urls.py
"""
Finance App URL Configuration
----------------------------
Defines all endpoints for quotations, invoices, expenses, financial reports,
client-facing portals, subscription management, bulk actions, CSV export,
and duplicate quotation.
"""

from django.urls import path
from .views import (
    # Quotations (staff)
    QuotationListView, QuotationCreateView, QuotationDetailView,
    QuotationUpdateView, QuotationSendView, QuotationConvertView, QuotationPDFView,
    DuplicateQuotationView,
    # Invoices (staff)
    InvoiceListView, InvoiceCreateView, InvoiceDetailView,
    AddInvoiceItemView, RecordPaymentView, IssueInvoiceView, InvoicePDFView,
    BulkInvoiceActionView, ExportInvoiceCSVView,
    # Expenses (staff)
    ExpenseListView, ExpenseCreateView, ApproveExpenseView, RejectExpenseView,
    # Reports
    ReportView,
    # Client-facing
    ClientInvoiceListView, ClientInvoiceDetailView,
    ClientQuotationListView, ClientQuotationDetailView,
    ClientQuotationApproveView, ClientQuotationRejectView,
    ClientSubscriptionDetailView, ClientSubscriptionUpgradeView, ClientSubscriptionCancelView,
)

urlpatterns = [
    # =========================================================================
    # Quotations (Staff only)
    # =========================================================================
    path('quotations/', QuotationListView.as_view(), name='quotation_list'),
    path('quotations/new/', QuotationCreateView.as_view(), name='quotation_create'),
    path('quotations/<int:pk>/', QuotationDetailView.as_view(), name='quotation_detail'),
    path('quotations/<int:pk>/edit/', QuotationUpdateView.as_view(), name='quotation_update'),
    path('quotations/<int:pk>/send/', QuotationSendView.as_view(), name='quotation_send'),
    path('quotations/<int:pk>/convert/', QuotationConvertView.as_view(), name='quotation_convert'),
    path('quotations/<int:pk>/duplicate/', DuplicateQuotationView.as_view(), name='quotation_duplicate'),
    path('quotations/<int:pk>/pdf/', QuotationPDFView.as_view(), name='quotation_pdf'),

    # =========================================================================
    # Invoices (Staff only)
    # =========================================================================
    path('invoices/', InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/new/', InvoiceCreateView.as_view(), name='invoice_create'),
    path('invoices/<int:pk>/', InvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<int:pk>/add-item/', AddInvoiceItemView.as_view(), name='invoice_add_item'),
    path('invoices/<int:pk>/payment/', RecordPaymentView.as_view(), name='invoice_payment'),
    path('invoices/<int:pk>/issue/', IssueInvoiceView.as_view(), name='invoice_issue'),
    path('invoices/<int:pk>/pdf/', InvoicePDFView.as_view(), name='invoice_pdf'),
    path('invoices/bulk-action/', BulkInvoiceActionView.as_view(), name='invoice_bulk_action'),
    path('invoices/export/', ExportInvoiceCSVView.as_view(), name='invoice_export_csv'),

    # =========================================================================
    # Expenses (Staff only)
    # =========================================================================
    path('expenses/', ExpenseListView.as_view(), name='expense_list'),
    path('expenses/new/', ExpenseCreateView.as_view(), name='expense_create'),
    path('expenses/<int:pk>/approve/', ApproveExpenseView.as_view(), name='expense_approve'),
    path('expenses/<int:pk>/reject/', RejectExpenseView.as_view(), name='expense_reject'),

    # =========================================================================
    # Financial Reports (Staff only)
    # =========================================================================
    path('reports/', ReportView.as_view(), name='finance_reports'),

    # =========================================================================
    # Client‑Facing Portal (read‑only + actions)
    # =========================================================================
    path('client/invoices/', ClientInvoiceListView.as_view(), name='client_invoice_list'),
    path('client/invoices/<int:pk>/', ClientInvoiceDetailView.as_view(), name='client_invoice_detail'),
    path('client/quotations/', ClientQuotationListView.as_view(), name='client_quotation_list'),
    path('client/quotations/<int:pk>/', ClientQuotationDetailView.as_view(), name='client_quotation_detail'),
    path('client/quotations/<int:pk>/approve/', ClientQuotationApproveView.as_view(), name='client_quotation_approve'),
    path('client/quotations/<int:pk>/reject/', ClientQuotationRejectView.as_view(), name='client_quotation_reject'),

    # =========================================================================
    # Subscription Management (Client‑facing)
    # =========================================================================
    path('client/subscription/', ClientSubscriptionDetailView.as_view(), name='client_subscription_detail'),
    path('client/subscription/change/', ClientSubscriptionUpgradeView.as_view(), name='client_subscription_change'),
    path('client/subscription/cancel/', ClientSubscriptionCancelView.as_view(), name='client_subscription_cancel'),
]