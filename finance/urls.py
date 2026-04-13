from django.urls import path
from .views import (ClientInvoiceDetailView, ClientInvoiceListView, ClientQuotationDetailView, ClientQuotationListView, InvoiceListView, InvoiceCreateView, InvoiceDetailView,
                    AddInvoiceItemView, QuotationConvertView, QuotationCreateView, QuotationDetailView, QuotationListView, QuotationSendView, QuotationUpdateView, RecordPaymentView, IssueInvoiceView,
                    ExpenseListView, ExpenseCreateView, InvoicePDFView,
                    ReportView)

urlpatterns = [
    # Quotations
    path('quotations/', QuotationListView.as_view(), name='quotation_list'),
    path('quotations/new/', QuotationCreateView.as_view(), name='quotation_create'),
    path('quotations/<int:pk>/', QuotationDetailView.as_view(), name='quotation_detail'),
    path('quotations/<int:pk>/edit/', QuotationUpdateView.as_view(), name='quotation_update'),
    path('quotations/<int:pk>/send/', QuotationSendView.as_view(), name='quotation_send'),
    path('quotations/<int:pk>/convert/', QuotationConvertView.as_view(), name='quotation_convert'),

    # Invoices (existing)
    path('invoices/', InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/new/', InvoiceCreateView.as_view(), name='invoice_create'),
    path('invoices/<int:pk>/', InvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<int:pk>/add-item/', AddInvoiceItemView.as_view(), name='invoice_add_item'),
    path('invoices/<int:pk>/payment/', RecordPaymentView.as_view(), name='invoice_payment'),
    path('invoices/<int:pk>/issue/', IssueInvoiceView.as_view(), name='invoice_issue'),
    path('invoices/<int:pk>/pdf/', InvoicePDFView.as_view(), name='invoice_pdf'),

    # Expenses
    path('expenses/', ExpenseListView.as_view(), name='expense_list'),
    path('expenses/new/', ExpenseCreateView.as_view(), name='expense_create'),

    # Reports
    path('reports/', ReportView.as_view(), name='finance_reports'),

    # Client-facing
    path('client/invoices/', ClientInvoiceListView.as_view(), name='client_invoice_list'),
    path('client/invoices/<int:pk>/', ClientInvoiceDetailView.as_view(), name='client_invoice_detail'),
    path('client/quotations/', ClientQuotationListView.as_view(), name='client_quotation_list'),
    path('client/quotations/<int:pk>/', ClientQuotationDetailView.as_view(), name='client_quotation_detail'),
]
