from django.urls import path
from .views import (InvoiceListView, InvoiceCreateView, InvoiceDetailView,
                    AddInvoiceItemView, RecordPaymentView, IssueInvoiceView,
                    ExpenseListView, ExpenseCreateView, InvoicePDFView,
                    ReportView)

urlpatterns = [
    path('invoices/', InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/new/', InvoiceCreateView.as_view(), name='invoice_create'),
    path('invoices/<int:pk>/', InvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<int:pk>/add-item/', AddInvoiceItemView.as_view(), name='invoice_add_item'),
    path('invoices/<int:pk>/payment/', RecordPaymentView.as_view(), name='invoice_payment'),
    path('invoices/<int:pk>/issue/', IssueInvoiceView.as_view(), name='invoice_issue'),
    path('expenses/', ExpenseListView.as_view(), name='expense_list'),
    path('expenses/new/', ExpenseCreateView.as_view(), name='expense_create'),
    path('invoices/<int:pk>/pdf/', InvoicePDFView.as_view(), name='invoice_pdf'),
    path('reports/', ReportView.as_view(), name='finance_reports'),
]
