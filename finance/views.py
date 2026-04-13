from django.views.generic import ListView, CreateView, DetailView, View, TemplateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import HttpResponse
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import json

from .models import Invoice, Expense, InvoiceItem, Quotation, QuotationItem
from .forms import (
    InvoiceForm, InvoiceItemForm, PaymentForm, ExpenseForm,
    QuotationForm, QuotationItemFormSet
)
from .services import InvoiceService, QuotationService
from infrastructure.pdf_service import render_pdf, pdf_response, pdf_inline_response
from core.models import SiteConfig
from core.mixins import RoleRequiredMixin
from .reports import ReportService


# ──────────────────────────────────────────────────────────────────────────────
# Quotation Views (Staff only)
# ──────────────────────────────────────────────────────────────────────────────

class QuotationListView(RoleRequiredMixin, ListView):
    model = Quotation
    template_name = 'finance/quotation_list.html'
    context_object_name = 'quotations'
    paginate_by = 20
    required_roles = ['FINANCE', 'ADMIN']

    def get_queryset(self):
        qs = Quotation.objects.select_related('client')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Quotation.STATUS_CHOICES
        ctx['current_status'] = self.request.GET.get('status', '')
        return ctx


class QuotationCreateView(RoleRequiredMixin, CreateView):
    model = Quotation
    form_class = QuotationForm
    template_name = 'finance/quotation_form.html'
    required_roles = ['FINANCE', 'ADMIN']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['items'] = QuotationItemFormSet(self.request.POST)
        else:
            ctx['items'] = QuotationItemFormSet()
        return ctx

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        with transaction.atomic():
            form.instance.created_by = self.request.user
            self.object = form.save()
            if items.is_valid():
                items.instance = self.object
                items.save()
                QuotationService.recalculate(self.object)
        messages.success(self.request, 'Quotation created.')
        return redirect('quotation_detail', pk=self.object.pk)


class QuotationDetailView(RoleRequiredMixin, DetailView):
    model = Quotation
    template_name = 'finance/quotation_detail.html'
    context_object_name = 'quotation'
    required_roles = ['FINANCE', 'ADMIN']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = self.object.items.all()
        ctx['config'] = SiteConfig.get()
        return ctx


class QuotationUpdateView(RoleRequiredMixin, UpdateView):
    model = Quotation
    form_class = QuotationForm
    template_name = 'finance/quotation_form.html'
    required_roles = ['FINANCE', 'ADMIN']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['items'] = QuotationItemFormSet(self.request.POST, instance=self.object)
        else:
            ctx['items'] = QuotationItemFormSet(instance=self.object)
        return ctx

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        with transaction.atomic():
            self.object = form.save()
            if items.is_valid():
                items.instance = self.object
                items.save()
                QuotationService.recalculate(self.object)
        messages.success(self.request, 'Quotation updated.')
        return redirect('quotation_detail', pk=self.object.pk)


class QuotationSendView(RoleRequiredMixin, View):
    required_roles = ['FINANCE', 'ADMIN']

    def post(self, request, pk):
        quotation = get_object_or_404(Quotation, pk=pk)
        try:
            QuotationService.send(quotation)
            messages.success(request, 'Quotation sent to client.')
        except ValueError as e:
            messages.error(request, str(e))
        return redirect('quotation_detail', pk=pk)


class QuotationConvertView(RoleRequiredMixin, View):
    required_roles = ['FINANCE', 'ADMIN']

    def post(self, request, pk):
        quotation = get_object_or_404(Quotation, pk=pk)
        try:
            invoice = QuotationService.convert_to_invoice(quotation, created_by=request.user)
            messages.success(request, f'Quotation converted to Invoice {invoice.invoice_number}.')
            return redirect('invoice_detail', pk=invoice.pk)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('quotation_detail', pk=pk)


# ──────────────────────────────────────────────────────────────────────────────
# Invoice Views (Staff only) — NOW WITH PERMISSION ENFORCEMENT
# ──────────────────────────────────────────────────────────────────────────────

class InvoiceListView(RoleRequiredMixin, ListView):
    model = Invoice
    template_name = 'finance/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20
    required_roles = ['FINANCE', 'ADMIN']

    def get_queryset(self):
        qs = Invoice.objects.select_related('client')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Invoice.STATUS_CHOICES
        ctx['current_status'] = self.request.GET.get('status', '')
        return ctx


class InvoiceCreateView(RoleRequiredMixin, CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'finance/invoice_form.html'
    success_url = reverse_lazy('invoice_list')
    required_roles = ['FINANCE', 'ADMIN']

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Invoice created. Add line items.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('invoice_detail', kwargs={'pk': self.object.pk})


class InvoiceDetailView(RoleRequiredMixin, DetailView):
    model = Invoice
    template_name = 'finance/invoice_detail.html'
    context_object_name = 'invoice'
    required_roles = ['FINANCE', 'ADMIN']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['item_form'] = InvoiceItemForm()
        ctx['payment_form'] = PaymentForm()
        ctx['items'] = self.object.items.all()
        ctx['payments'] = self.object.payments.all()
        ctx['config'] = SiteConfig.get()
        return ctx


class AddInvoiceItemView(RoleRequiredMixin, View):
    required_roles = ['FINANCE', 'ADMIN']

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        form = InvoiceItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.invoice = invoice
            item.save()
            InvoiceService.recalculate(invoice)
        return redirect('invoice_detail', pk=pk)


class RecordPaymentView(RoleRequiredMixin, View):
    required_roles = ['FINANCE', 'ADMIN']

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        form = PaymentForm(request.POST)
        if form.is_valid():
            InvoiceService.record_payment(
                invoice=invoice,
                recorded_by=request.user,
                **form.cleaned_data
            )
            messages.success(request, 'Payment recorded.')
        return redirect('invoice_detail', pk=pk)


class IssueInvoiceView(RoleRequiredMixin, View):
    required_roles = ['FINANCE', 'ADMIN']

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        try:
            InvoiceService.issue(invoice)
            messages.success(request, 'Invoice issued.')
        except ValueError as e:
            messages.error(request, str(e))
        return redirect('invoice_detail', pk=pk)


class InvoicePDFView(RoleRequiredMixin, View):
    """Generate a branded PDF for the invoice."""
    required_roles = ['FINANCE', 'ADMIN']

    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        config = SiteConfig.get()
        vat_percent = float(config.vat_rate) * 100

        pdf_bytes = render_pdf('finance/invoice_pdf.html', {
            'invoice': invoice,
            'items': invoice.items.all(),
            'config': config,
            'vat_percent': f'{vat_percent:.1f}',
        })

        filename = f'{invoice.invoice_number}.pdf'
        action = request.GET.get('action', 'download')
        if action == 'view':
            return pdf_inline_response(pdf_bytes, filename)
        return pdf_response(pdf_bytes, filename)


# ──────────────────────────────────────────────────────────────────────────────
# Expense Views (Staff only)
# ──────────────────────────────────────────────────────────────────────────────

class ExpenseListView(RoleRequiredMixin, ListView):
    model = Expense
    template_name = 'finance/expense_list.html'
    context_object_name = 'expenses'
    paginate_by = 20
    required_roles = ['FINANCE', 'ADMIN']


class ExpenseCreateView(RoleRequiredMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'finance/expense_form.html'
    success_url = reverse_lazy('expense_list')
    required_roles = ['FINANCE', 'ADMIN']

    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        return super().form_valid(form)


# ──────────────────────────────────────────────────────────────────────────────
# Report Views (Staff only)
# ──────────────────────────────────────────────────────────────────────────────

class ReportView(RoleRequiredMixin, TemplateView):
    template_name = 'finance/reports.html'
    required_roles = ['FINANCE', 'ADMIN']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        period = self.request.GET.get('period', 'this_month')
        start, end = ReportService.date_range(period)

        ctx['period'] = period
        ctx['start'] = start
        ctx['end'] = end
        ctx['income'] = ReportService.income_statement(start, end)
        ctx['aging'] = ReportService.accounts_receivable_aging()
        ctx['top_clients'] = ReportService.client_revenue(start, end)
        ctx['monthly'] = ReportService.monthly_revenue(6)
        ctx['monthly_json'] = json.dumps(ctx['monthly'])
        ctx['config'] = SiteConfig.get()
        ctx['period_choices'] = [
            ('this_month', 'This Month'),
            ('last_month', 'Last Month'),
            ('last_30', 'Last 30 Days'),
            ('last_90', 'Last 90 Days'),
            ('this_quarter', 'This Quarter'),
            ('this_year', 'This Year'),
        ]
        return ctx


# ──────────────────────────────────────────────────────────────────────────────
# Client-Facing Views (read-only access to own invoices/quotations)
# ──────────────────────────────────────────────────────────────────────────────
# finance/views.py (excerpt)

class ClientInvoiceListView(LoginRequiredMixin, ListView):
    template_name = 'finance/client_invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20

    def get_queryset(self):
        if hasattr(self.request.user, 'client_organization'):
            client_org = self.request.user.client_organization
            return Invoice.objects.filter(client=client_org).order_by('-created_at')
        return Invoice.objects.none()


class ClientInvoiceDetailView(LoginRequiredMixin, DetailView):
    template_name = 'finance/client_invoice_detail.html'
    context_object_name = 'invoice'

    def get_queryset(self):
        if hasattr(self.request.user, 'client_organization'):
            client_org = self.request.user.client_organization
            return Invoice.objects.filter(client=client_org)
        return Invoice.objects.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['config'] = SiteConfig.get()
        ctx['items'] = self.object.items.all()
        ctx['payments'] = self.object.payments.all()
        return ctx


class ClientQuotationListView(LoginRequiredMixin, ListView):
    template_name = 'finance/client_quotation_list.html'
    context_object_name = 'quotations'
    paginate_by = 20

    def get_queryset(self):
        if hasattr(self.request.user, 'client_organization'):
            client_org = self.request.user.client_organization
            return Quotation.objects.filter(client=client_org).order_by('-created_at')
        return Quotation.objects.none()


class ClientQuotationDetailView(LoginRequiredMixin, DetailView):
    template_name = 'finance/client_quotation_detail.html'
    context_object_name = 'quotation'

    def get_queryset(self):
        if hasattr(self.request.user, 'client_organization'):
            client_org = self.request.user.client_organization
            return Quotation.objects.filter(client=client_org)
        return Quotation.objects.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['config'] = SiteConfig.get()
        ctx['items'] = self.object.items.all()
        return ctx

# class ClientInvoiceListView(LoginRequiredMixin, ListView):
#     template_name = 'finance/client_invoice_list.html'
#     context_object_name = 'invoices'
#     paginate_by = 20

#     def get_queryset(self):
#         # Assumes client user is linked to a ClientOrganization via user.client_organization
#         # Adjust according to your actual relationship
#         if hasattr(self.request.user, 'client_organization'):
#             client_org = self.request.user.client_organization
#             return Invoice.objects.filter(client=client_org).order_by('-created_at')
#         return Invoice.objects.none()


# class ClientInvoiceDetailView(LoginRequiredMixin, DetailView):
#     template_name = 'finance/client_invoice_detail.html'
#     context_object_name = 'invoice'

#     def get_queryset(self):
#         if hasattr(self.request.user, 'client_organization'):
#             client_org = self.request.user.client_organization
#             return Invoice.objects.filter(client=client_org)
#         return Invoice.objects.none()

#     def get_context_data(self, **kwargs):
#         ctx = super().get_context_data(**kwargs)
#         ctx['config'] = SiteConfig.get()
#         ctx['items'] = self.object.items.all()
#         ctx['payments'] = self.object.payments.all()
#         return ctx


# class ClientQuotationListView(LoginRequiredMixin, ListView):
#     template_name = 'finance/client_quotation_list.html'
#     context_object_name = 'quotations'
#     paginate_by = 20

#     def get_queryset(self):
#         if hasattr(self.request.user, 'client_organization'):
#             client_org = self.request.user.client_organization
#             return Quotation.objects.filter(client=client_org).order_by('-created_at')
#         return Quotation.objects.none()


# class ClientQuotationDetailView(LoginRequiredMixin, DetailView):
#     template_name = 'finance/client_quotation_detail.html'
#     context_object_name = 'quotation'

#     def get_queryset(self):
#         if hasattr(self.request.user, 'client_organization'):
#             client_org = self.request.user.client_organization
#             return Quotation.objects.filter(client=client_org)
#         return Quotation.objects.none()

#     def get_context_data(self, **kwargs):
#         ctx = super().get_context_data(**kwargs)
#         ctx['config'] = SiteConfig.get()
#         ctx['items'] = self.object.items.all()
#         return ctx