# finance/urls.py
"""
Finance App URL Configuration
==============================

Routes are grouped by domain:

- Quotations (staff)
- Invoices   (staff)
- Receipts   (staff)   ← auto-issued when an invoice is fully paid
- Expenses   (staff)
- Reports    (staff)
- Client portal (invoices, quotations, receipts, subscriptions)
- HTMX endpoints
"""

from django.urls import path

from .views import (
    # ---------------- Quotations ----------------
    QuotationListView, QuotationCreateView, QuotationDetailView,
    QuotationUpdateView, QuotationSendView, QuotationConvertView,
    QuotationPDFView, DuplicateQuotationView, QuotationDeleteView,
    quotation_print_view, quotation_pdf_direct,
    quotation_word_export, quotation_excel_export,

    # ---------------- Invoices ----------------
    InvoiceListView, InvoiceCreateView, InvoiceDetailView,
    AddInvoiceItemView, RecordPaymentView, IssueInvoiceView,
    InvoicePDFView, BulkInvoiceActionView, ExportInvoiceCSVView,
    invoice_pdf_direct, invoice_excel_export,

    # ---------------- Receipts ----------------
    ReceiptListView, ReceiptDetailView, receipt_pdf_direct,

    # ---------------- Expenses ----------------
    ExpenseListView, ExpenseCreateView,
    ApproveExpenseView, RejectExpenseView,

    # ---------------- Reports ----------------
    ReportView,

    # ---------------- Client-facing ----------------
    ClientInvoiceListView, ClientInvoiceDetailView,
    ClientQuotationListView, ClientQuotationDetailView,
    ClientQuotationApproveView, ClientQuotationRejectView,
    ClientReceiptListView, ClientReceiptDetailView,
    ClientSubscriptionDetailView, ClientSubscriptionUpgradeView,
    ClientSubscriptionCancelView,

    # ---------------- HTMX ----------------
    live_quotation_search, update_quotation_status, live_invoice_search,
)


urlpatterns = [
    # =========================================================================
    # QUOTATIONS (staff)
    # =========================================================================
    path('quotations/', QuotationListView.as_view(), name='quotation_list'),
    path('quotations/new/', QuotationCreateView.as_view(), name='quotation_create'),
    path('quotations/<int:pk>/', QuotationDetailView.as_view(), name='quotation_detail'),
    path('quotations/<int:pk>/edit/', QuotationUpdateView.as_view(), name='quotation_update'),
    path('quotations/<int:pk>/send/', QuotationSendView.as_view(), name='quotation_send'),
    path('quotations/<int:pk>/convert/', QuotationConvertView.as_view(), name='quotation_convert'),
    path('quotations/<int:pk>/duplicate/', DuplicateQuotationView.as_view(), name='quotation_duplicate'),
    path('quotations/<int:pk>/delete/', QuotationDeleteView.as_view(), name='quotation_delete'),
    path('quotations/<int:pk>/pdf/', QuotationPDFView.as_view(), name='quotation_pdf'),
    path('quotations/<int:pk>/pdf-direct/', quotation_pdf_direct, name='quotation_pdf_direct'),
    path('quotations/<int:pk>/print/', quotation_print_view, name='quotation_print'),
    path('quotations/<int:pk>/word/', quotation_word_export, name='quotation_word'),
    path('quotations/<int:pk>/excel/', quotation_excel_export, name='quotation_excel'),

    # =========================================================================
    # INVOICES (staff)
    # =========================================================================
    path('invoices/', InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/new/', InvoiceCreateView.as_view(), name='invoice_create'),
    path('invoices/<int:pk>/', InvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<int:pk>/add-item/', AddInvoiceItemView.as_view(), name='invoice_add_item'),
    path('invoices/<int:pk>/payment/', RecordPaymentView.as_view(), name='invoice_payment'),
    path('invoices/<int:pk>/issue/', IssueInvoiceView.as_view(), name='invoice_issue'),
    path('invoices/<int:pk>/pdf/', InvoicePDFView.as_view(), name='invoice_pdf'),
    path('invoices/<int:pk>/pdf-direct/', invoice_pdf_direct, name='invoice_pdf_direct'),
    path('invoices/<int:pk>/excel/', invoice_excel_export, name='invoice_excel'),
    path('invoices/bulk-action/', BulkInvoiceActionView.as_view(), name='invoice_bulk_action'),
    path('invoices/export/', ExportInvoiceCSVView.as_view(), name='invoice_export_csv'),

    # =========================================================================
    # RECEIPTS (staff)
    # =========================================================================
    path('receipts/', ReceiptListView.as_view(), name='receipt_list'),
    path('receipts/<int:pk>/', ReceiptDetailView.as_view(), name='receipt_detail'),
    path('receipts/<int:pk>/pdf/', receipt_pdf_direct, name='receipt_pdf_direct'),

    # =========================================================================
    # EXPENSES (staff)
    # =========================================================================
    path('expenses/', ExpenseListView.as_view(), name='expense_list'),
    path('expenses/new/', ExpenseCreateView.as_view(), name='expense_create'),
    path('expenses/<int:pk>/approve/', ApproveExpenseView.as_view(), name='expense_approve'),
    path('expenses/<int:pk>/reject/', RejectExpenseView.as_view(), name='expense_reject'),

    # =========================================================================
    # REPORTS (staff)
    # =========================================================================
    path('reports/', ReportView.as_view(), name='finance_reports'),

    # =========================================================================
    # CLIENT PORTAL – INVOICES
    # =========================================================================
    path('client/invoices/', ClientInvoiceListView.as_view(), name='client_invoice_list'),
    path('client/invoices/<int:pk>/', ClientInvoiceDetailView.as_view(), name='client_invoice_detail'),

    # =========================================================================
    # CLIENT PORTAL – QUOTATIONS
    # =========================================================================
    path('client/quotations/', ClientQuotationListView.as_view(), name='client_quotation_list'),
    path('client/quotations/<int:pk>/', ClientQuotationDetailView.as_view(), name='client_quotation_detail'),
    path('client/quotations/<int:pk>/approve/', ClientQuotationApproveView.as_view(), name='client_quotation_approve'),
    path('client/quotations/<int:pk>/reject/', ClientQuotationRejectView.as_view(), name='client_quotation_reject'),

    # =========================================================================
    # CLIENT PORTAL – RECEIPTS
    # =========================================================================
    path('client/receipts/', ClientReceiptListView.as_view(), name='client_receipt_list'),
    path('client/receipts/<int:pk>/', ClientReceiptDetailView.as_view(), name='client_receipt_detail'),

    # =========================================================================
    # CLIENT PORTAL – SUBSCRIPTIONS
    # =========================================================================
    path('client/subscription/', ClientSubscriptionDetailView.as_view(), name='client_subscription_detail'),
    path('client/subscription/change/', ClientSubscriptionUpgradeView.as_view(), name='client_subscription_change'),
    path('client/subscription/cancel/', ClientSubscriptionCancelView.as_view(), name='client_subscription_cancel'),

    # =========================================================================
    # HTMX ENDPOINTS
    # =========================================================================
    path('htmx/quotation-search/', live_quotation_search, name='live_quotation_search'),
    path('htmx/quotation-status/<int:pk>/', update_quotation_status, name='update_quotation_status'),
    path('htmx/invoice-search/', live_invoice_search, name='live_invoice_search'),
]