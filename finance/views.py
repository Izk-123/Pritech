# finance/views.py
"""
Finance App Views
-----------------
Handles quotations, invoices, expenses, financial reports, client-facing portals,
subscription management, and async PDF generation. Added enhancements:
- Invoice list with date range filters, totals row, bulk actions (reminder/issue)
- Duplicate quotation functionality
- CSV export for invoices
"""

import base64
import csv
import json
import logging
from datetime import date, timedelta

from django.views.generic import ListView, CreateView, DetailView, View, TemplateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import HttpResponse, Http404
from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.utils.decorators import method_decorator

from .models import Invoice, Expense, InvoiceItem, Quotation, QuotationItem, Plan, ClientSubscription
from .forms import (
    InvoiceForm, InvoiceItemForm, PaymentForm, ExpenseForm,
    QuotationForm, QuotationItemFormSet, SubscriptionChangeForm
)
from .services import InvoiceService, QuotationService
from infrastructure.pdf_service import render_pdf, pdf_response, pdf_inline_response
from core.models import SiteConfig
from core.mixins import RoleRequiredMixin
from .reports import ReportService
from .tasks import generate_invoice_pdf, generate_quotation_pdf

from infrastructure.pdf_sanitizer import sanitize_html, sanitize_plain_text
from accounts.decorators import rate_limit, get_client_ip

logger = logging.getLogger(__name__)


# =============================================================================
# Helper: Send payment reminder email
# =============================================================================
def send_payment_reminder(invoice):
    """Send an email reminder to the client about an overdue or outstanding invoice."""
    try:
        from django.core.mail import send_mail
        config = SiteConfig.get()
        subject = f"Payment Reminder: {invoice.invoice_number}"
        message = (
            f"Dear {invoice.client.name},\n\n"
            f"Invoice {invoice.invoice_number} of amount {config.currency_symbol}{invoice.balance_due} "
            f"is due on {invoice.due_date}. Please arrange payment.\n\n"
            f"Thank you for your business.\n\n"
            f"{config.company_name}"
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=config.email or settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invoice.client.email],
            fail_silently=True,
        )
    except Exception as e:
        logger.warning(f"Failed to send payment reminder for {invoice.invoice_number}: {e}")


# =============================================================================
# QUOTATION VIEWS (Staff only)
# =============================================================================

class QuotationListView(RoleRequiredMixin, ListView):
    """List all quotations with filtering by status."""
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
    """Create a new quotation with inline line items."""
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
    """View quotation details (staff side)."""
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
    """Edit an existing quotation (only draft status)."""
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
    """Send quotation to client (changes status to 'sent')."""
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
    """Convert an approved quotation into an invoice."""
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


class DuplicateQuotationView(RoleRequiredMixin, View):
    """Create a new draft quotation by copying an existing one."""
    required_roles = ['FINANCE', 'ADMIN']

    def post(self, request, pk):
        original = get_object_or_404(Quotation, pk=pk)
        new_quotation = Quotation.objects.create(
            client=original.client,
            issue_date=date.today(),
            valid_until=date.today() + timedelta(days=30),
            notes=f"Duplicated from {original.quotation_number}",
            created_by=request.user,
            status='draft'
        )
        for item in original.items.all():
            QuotationItem.objects.create(
                quotation=new_quotation,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total=item.total
            )
        QuotationService.recalculate(new_quotation)
        messages.success(request, f'Quotation duplicated as {new_quotation.quotation_number}.')
        return redirect('quotation_detail', pk=new_quotation.pk)


@method_decorator(rate_limit(key_func=get_client_ip, rate='30/h', method='GET', block=True), name='dispatch')
class QuotationPDFView(RoleRequiredMixin, View):
    """Asynchronous PDF generation for quotations."""
    required_roles = ['FINANCE', 'ADMIN']

    def get(self, request, pk):
        cache_key = f'quotation_pdf_{pk}'
        pdf_bytes = cache.get(cache_key)
        if pdf_bytes:
            return pdf_response(pdf_bytes, f'Quotation_{pk}.pdf')
        generate_quotation_pdf.delay(pk)
        return HttpResponse(
            'PDF is being generated. Please refresh in a few moments.',
            status=202,
            content_type='text/plain'
        )


# =============================================================================
# INVOICE VIEWS (Staff only)
# =============================================================================

class InvoiceListView(RoleRequiredMixin, ListView):
    """
    List all invoices with filtering by status, issue date range, due date range.
    Includes totals row and pagination.
    """
    model = Invoice
    template_name = 'finance/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20
    required_roles = ['FINANCE', 'ADMIN']

    def get_queryset(self):
        qs = Invoice.objects.select_related('client')
        # Status filter
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        # Issue date range
        issue_from = self.request.GET.get('issue_from')
        if issue_from:
            qs = qs.filter(issue_date__gte=issue_from)
        issue_to = self.request.GET.get('issue_to')
        if issue_to:
            qs = qs.filter(issue_date__lte=issue_to)
        # Due date range
        due_from = self.request.GET.get('due_from')
        if due_from:
            qs = qs.filter(due_date__gte=due_from)
        due_to = self.request.GET.get('due_to')
        if due_to:
            qs = qs.filter(due_date__lte=due_to)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Invoice.STATUS_CHOICES
        ctx['current_status'] = self.request.GET.get('status', '')
        # Preserve filter values in template
        ctx['issue_from'] = self.request.GET.get('issue_from', '')
        ctx['issue_to'] = self.request.GET.get('issue_to', '')
        ctx['due_from'] = self.request.GET.get('due_from', '')
        ctx['due_to'] = self.request.GET.get('due_to', '')
        # Compute totals for the filtered queryset
        qs = self.get_queryset()
        ctx['total_amount_sum'] = qs.aggregate(total=models.Sum('total_amount'))['total'] or 0
        ctx['total_paid_sum'] = qs.aggregate(total=models.Sum('amount_paid'))['total'] or 0
        ctx['total_balance_sum'] = ctx['total_amount_sum'] - ctx['total_paid_sum']
        return ctx


class InvoiceCreateView(RoleRequiredMixin, CreateView):
    """Create a new draft invoice."""
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
    """Invoice detail page with items and payments."""
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
    """Add a line item to a draft invoice."""
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
    """Record a payment against an invoice with idempotency lock."""
    required_roles = ['FINANCE', 'ADMIN']

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        lock_key = f"payment_lock_{invoice.pk}_{request.user.pk}"
        if cache.get(lock_key):
            messages.error(request, "You are recording payments too quickly. Please wait a moment.")
            return redirect('invoice_detail', pk=pk)

        form = PaymentForm(request.POST)
        if form.is_valid():
            cache.set(lock_key, True, timeout=5)
            InvoiceService.record_payment(
                invoice=invoice,
                recorded_by=request.user,
                **form.cleaned_data
            )
            messages.success(request, 'Payment recorded.')
        else:
            messages.error(request, 'Invalid payment data.')
        return redirect('invoice_detail', pk=pk)


class IssueInvoiceView(RoleRequiredMixin, View):
    """Change invoice status from draft to issued (after totals validation)."""
    required_roles = ['FINANCE', 'ADMIN']

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        try:
            InvoiceService.issue(invoice)
            messages.success(request, 'Invoice issued.')
        except ValueError as e:
            messages.error(request, str(e))
        return redirect('invoice_detail', pk=pk)


class BulkInvoiceActionView(RoleRequiredMixin, View):
    """Bulk actions: send payment reminders or issue multiple invoices."""
    required_roles = ['FINANCE', 'ADMIN']

    def post(self, request):
        action = request.POST.get('action')
        invoice_ids = request.POST.getlist('invoice_ids')
        if not invoice_ids:
            messages.error(request, 'No invoices selected.')
            return redirect(request.META.get('HTTP_REFERER', 'invoice_list'))

        invoices = Invoice.objects.filter(pk__in=invoice_ids)
        if action == 'send_reminder':
            for inv in invoices:
                send_payment_reminder(inv)
            messages.success(request, f'Reminder sent to {len(invoices)} client(s).')
        elif action == 'issue':
            count = 0
            for inv in invoices:
                if inv.status == 'draft':
                    InvoiceService.issue(inv)
                    count += 1
            messages.success(request, f'{count} invoice(s) issued.')
        else:
            messages.error(request, 'Invalid action.')
        return redirect(request.META.get('HTTP_REFERER', 'invoice_list'))


class ExportInvoiceCSVView(RoleRequiredMixin, View):
    """Export filtered invoice list to CSV."""
    required_roles = ['FINANCE', 'ADMIN']

    def get(self, request):
        # Apply same filters as InvoiceListView
        qs = Invoice.objects.select_related('client')
        status = request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        issue_from = request.GET.get('issue_from')
        if issue_from:
            qs = qs.filter(issue_date__gte=issue_from)
        issue_to = request.GET.get('issue_to')
        if issue_to:
            qs = qs.filter(issue_date__lte=issue_to)
        due_from = request.GET.get('due_from')
        if due_from:
            qs = qs.filter(due_date__gte=due_from)
        due_to = request.GET.get('due_to')
        if due_to:
            qs = qs.filter(due_date__lte=due_to)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="invoices.csv"'
        writer = csv.writer(response)
        writer.writerow(['Invoice #', 'Client', 'Issue Date', 'Due Date', 'Total', 'Paid', 'Balance', 'Status'])
        for inv in qs:
            writer.writerow([
                inv.invoice_number,
                inv.client.name,
                inv.issue_date,
                inv.due_date,
                inv.total_amount,
                inv.amount_paid,
                inv.balance_due,
                inv.get_status_display()
            ])
        return response


@method_decorator(rate_limit(key_func=get_client_ip, rate='30/h', method='GET', block=True), name='dispatch')
class InvoicePDFView(RoleRequiredMixin, View):
    """Asynchronous PDF generation for invoices."""
    required_roles = ['FINANCE', 'ADMIN']

    def get(self, request, pk):
        cache_key = f'invoice_pdf_{pk}'
        pdf_bytes = cache.get(cache_key)
        if pdf_bytes:
            return pdf_response(pdf_bytes, f'Invoice_{pk}.pdf')
        generate_invoice_pdf.delay(pk)
        return HttpResponse(
            'PDF is being generated. Please refresh in a few moments.',
            status=202,
            content_type='text/plain'
        )


# =============================================================================
# EXPENSE VIEWS (Staff only)
# =============================================================================

class ExpenseListView(RoleRequiredMixin, ListView):
    """List all expenses with approval status."""
    model = Expense
    template_name = 'finance/expense_list.html'
    context_object_name = 'expenses'
    paginate_by = 20
    required_roles = ['FINANCE', 'ADMIN']


class ExpenseCreateView(RoleRequiredMixin, CreateView):
    """Create a new expense (pending approval by default)."""
    model = Expense
    form_class = ExpenseForm
    template_name = 'finance/expense_form.html'
    success_url = reverse_lazy('expense_list')
    required_roles = ['FINANCE', 'ADMIN']

    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        return super().form_valid(form)


class ApproveExpenseView(RoleRequiredMixin, View):
    """Approve a pending expense."""
    required_roles = ['FINANCE', 'ADMIN']

    def post(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        if expense.status != 'pending':
            messages.error(request, 'This expense is already processed.')
            return redirect('expense_list')
        expense.status = 'approved'
        expense.approved_by = request.user
        expense.approved_at = timezone.now()
        expense.save()
        messages.success(request, f'Expense "{expense.description}" approved.')
        return redirect('expense_list')


class RejectExpenseView(RoleRequiredMixin, View):
    """Reject a pending expense."""
    required_roles = ['FINANCE', 'ADMIN']

    def post(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        if expense.status != 'pending':
            messages.error(request, 'This expense is already processed.')
            return redirect('expense_list')
        expense.status = 'rejected'
        expense.save()
        messages.warning(request, f'Expense "{expense.description}" rejected.')
        return redirect('expense_list')


# =============================================================================
# FINANCIAL REPORTS (Staff only)
# =============================================================================

class ReportView(RoleRequiredMixin, TemplateView):
    """Financial dashboard with charts, aging, and top clients."""
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


# =============================================================================
# CLIENT-FACING VIEWS (with object‑level permissions)
# =============================================================================

class ClientInvoiceListView(LoginRequiredMixin, ListView):
    """Clients see only their own invoices."""
    template_name = 'finance/client_invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20

    def get_queryset(self):
        client_org = getattr(self.request.user, 'client_organization', None)
        if not client_org:
            return Invoice.objects.none()
        return Invoice.objects.filter(client=client_org).order_by('-created_at')


class ClientInvoiceDetailView(LoginRequiredMixin, DetailView):
    """Client invoice detail with permission check."""
    template_name = 'finance/client_invoice_detail.html'
    context_object_name = 'invoice'

    def get_queryset(self):
        client_org = getattr(self.request.user, 'client_organization', None)
        if not client_org:
            return Invoice.objects.none()
        return Invoice.objects.filter(client=client_org)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.client != getattr(self.request.user, 'client_organization', None):
            raise Http404("Invoice not found.")
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['config'] = SiteConfig.get()
        ctx['items'] = self.object.items.all()
        ctx['payments'] = self.object.payments.all()
        return ctx


class ClientQuotationListView(LoginRequiredMixin, ListView):
    """Clients see only their own quotations."""
    template_name = 'finance/client_quotation_list.html'
    context_object_name = 'quotations'
    paginate_by = 20

    def get_queryset(self):
        client_org = getattr(self.request.user, 'client_organization', None)
        if not client_org:
            return Quotation.objects.none()
        return Quotation.objects.filter(client=client_org).order_by('-created_at')


class ClientQuotationDetailView(LoginRequiredMixin, DetailView):
    """Client quotation detail with permission check."""
    template_name = 'finance/client_quotation_detail.html'
    context_object_name = 'quotation'

    def get_queryset(self):
        client_org = getattr(self.request.user, 'client_organization', None)
        if not client_org:
            return Quotation.objects.none()
        return Quotation.objects.filter(client=client_org)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.client != getattr(self.request.user, 'client_organization', None):
            raise Http404("Quotation not found.")
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['config'] = SiteConfig.get()
        ctx['items'] = self.object.items.all()
        return ctx


class ClientQuotationApproveView(LoginRequiredMixin, View):
    """Client approves a sent quotation, automatically creating an invoice."""
    def post(self, request, pk):
        quotation = get_object_or_404(Quotation, pk=pk, client=request.user.client_organization)
        if quotation.status != 'sent':
            messages.error(request, f"This quotation cannot be approved (current status: {quotation.status}).")
            return redirect('client_quotation_detail', pk=pk)

        quotation.status = 'approved'
        quotation.save(update_fields=['status'])
        try:
            invoice = QuotationService.convert_to_invoice(quotation, created_by=request.user)
            messages.success(request, f"Quotation {quotation.quotation_number} approved and converted to invoice {invoice.invoice_number}.")
            return redirect('client_invoice_detail', pk=invoice.pk)
        except ValueError as e:
            messages.error(request, f"Conversion failed: {e}")
            quotation.status = 'sent'
            quotation.save(update_fields=['status'])
            return redirect('client_quotation_detail', pk=pk)


class ClientQuotationRejectView(LoginRequiredMixin, View):
    """Client rejects a sent quotation with a reason (stored as feedback)."""
    def post(self, request, pk):
        quotation = get_object_or_404(Quotation, pk=pk, client=request.user.client_organization)
        if quotation.status != 'sent':
            messages.error(request, "This quotation cannot be rejected.")
            return redirect('client_quotation_detail', pk=pk)

        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, "Please provide a reason for rejection or change request.")
            return redirect('client_quotation_detail', pk=pk)

        quotation.status = 'rejected'
        quotation.client_feedback = reason
        quotation.save(update_fields=['status', 'client_feedback'])

        # Optional email notification to finance
        try:
            from django.core.mail import send_mail
            config = SiteConfig.get()
            send_mail(
                subject=f"Quotation {quotation.quotation_number} rejected by {quotation.client.name}",
                message=f"Client feedback:\n{reason}",
                from_email=config.email or settings.DEFAULT_FROM_EMAIL,
                recipient_list=['finance@pritech.mw'],
                fail_silently=True,
            )
        except Exception:
            pass

        messages.success(request, "Quotation rejected. We'll review your feedback and get back to you.")
        return redirect('client_quotation_detail', pk=pk)


class ClientSubscriptionDetailView(LoginRequiredMixin, DetailView):
    """Display client's current subscription details."""
    template_name = 'finance/client_subscription_detail.html'
    context_object_name = 'subscription'

    def get_object(self, queryset=None):
        client_org = getattr(self.request.user, 'client_organization', None)
        if not client_org:
            raise Http404("No subscription found for your organization.")
        return get_object_or_404(ClientSubscription, client=client_org)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['available_plans'] = Plan.objects.filter(is_active=True).exclude(pk=self.object.plan.pk)
        return ctx


class ClientSubscriptionUpgradeView(LoginRequiredMixin, UpdateView):
    """Upgrade or schedule downgrade of subscription plan."""
    model = ClientSubscription
    form_class = SubscriptionChangeForm
    template_name = 'finance/client_subscription_form.html'
    success_url = reverse_lazy('client_subscription_detail')

    def get_object(self, queryset=None):
        client_org = getattr(self.request.user, 'client_organization', None)
        if not client_org:
            raise Http404("No subscription found.")
        return get_object_or_404(ClientSubscription, client=client_org)

    def form_valid(self, form):
        new_plan = form.cleaned_data['plan']
        subscription = self.get_object()
        if new_plan.monthly_price > subscription.plan.monthly_price:
            # Upgrade immediately
            subscription.plan = new_plan
            subscription.save()
            messages.success(self.request, f"Plan upgraded to {new_plan.name}.")
        else:
            # Downgrade at period end
            subscription.cancel_at_period_end = True
            subscription.save()
            messages.info(self.request, f"Plan will downgrade to {new_plan.name} at the end of current period.")
        return redirect(self.success_url)


class ClientSubscriptionCancelView(LoginRequiredMixin, View):
    """Cancel subscription at the end of current billing period."""
    def post(self, request):
        client_org = getattr(request.user, 'client_organization', None)
        if not client_org:
            messages.error(request, "No active subscription found.")
            return redirect('client_subscription_detail')
        subscription = get_object_or_404(ClientSubscription, client=client_org)
        subscription.cancel_at_period_end = True
        subscription.save()
        messages.warning(request, "Your subscription will be cancelled at the end of the current billing period.")
        return redirect('client_subscription_detail')