from django.views.generic import ListView, CreateView, DetailView, View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import HttpResponse
from .models import Invoice, Expense, InvoiceItem
from .forms import InvoiceForm, InvoiceItemForm, PaymentForm, ExpenseForm
from .services import InvoiceService
import json


class InvoiceListView(LoginRequiredMixin, ListView):
    model = Invoice
    template_name = 'finance/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20

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


class InvoiceCreateView(LoginRequiredMixin, CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'finance/invoice_form.html'
    success_url = reverse_lazy('invoice_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Invoice created. Add line items.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('invoice_detail', kwargs={'pk': self.object.pk})


class InvoiceDetailView(LoginRequiredMixin, DetailView):
    model = Invoice
    template_name = 'finance/invoice_detail.html'
    context_object_name = 'invoice'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['item_form'] = InvoiceItemForm()
        ctx['payment_form'] = PaymentForm()
        ctx['items'] = self.object.items.all()
        ctx['payments'] = self.object.payments.all()
        return ctx


class AddInvoiceItemView(LoginRequiredMixin, View):
    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        form = InvoiceItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.invoice = invoice
            item.save()
            InvoiceService.recalculate(invoice)
        return redirect('invoice_detail', pk=pk)


class RecordPaymentView(LoginRequiredMixin, View):
    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        form = PaymentForm(request.POST)
        if form.is_valid():
            InvoiceService.record_payment(
                invoice=invoice, recorded_by=request.user, **form.cleaned_data
            )
            messages.success(request, 'Payment recorded.')
        return redirect('invoice_detail', pk=pk)


class IssueInvoiceView(LoginRequiredMixin, View):
    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        try:
            InvoiceService.issue(invoice)
            messages.success(request, 'Invoice issued.')
        except ValueError as e:
            messages.error(request, str(e))
        return redirect('invoice_detail', pk=pk)


class ExpenseListView(LoginRequiredMixin, ListView):
    model = Expense
    template_name = 'finance/expense_list.html'
    context_object_name = 'expenses'
    paginate_by = 20


class ExpenseCreateView(LoginRequiredMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'finance/expense_form.html'
    success_url = reverse_lazy('expense_list')

    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        return super().form_valid(form)


from infrastructure.pdf_service import render_pdf, pdf_response, pdf_inline_response
from core.models import SiteConfig


class InvoicePDFView(LoginRequiredMixin, View):
    """Generate a branded PDF for the invoice."""

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


import json
from .reports import ReportService


class ReportView(LoginRequiredMixin, TemplateView):
    template_name = 'finance/reports.html'

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
