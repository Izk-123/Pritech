# finance/views.py
"""
Finance App Views
-----------------
Complete set of views for financial management:

- Quotations (CRUD, send, convert, duplicate, delete, PDF, print, Word, Excel)
- Invoices   (CRUD, add items, record payment, issue, bulk actions, CSV, PDF, Excel)
- Receipts   (list, detail, PDF download) — auto-created when invoice is paid
- Expenses   (list, create, approve, reject)
- Financial Reports
- Client portal (invoices, quotations, receipts, approve/reject, subscription)
- HTMX real-time endpoints

Excel exports follow the printable invoice template layout:
- Vertical rotated "INVOICE"/"QUOTATION" label on the left (column B)
- Company block (column C) with logo top-right
- BILL TO / LOCATION / Dates three-column layout
- Blue table header with DESCRIPTION | QTY | UNIT PRICE | TOTAL
- Totals block with SUBTOTAL / DISCOUNT / TAX RATE / TOTAL TAX / Balance Due
- Thank-you line and Terms & Instructions footer
"""

import csv
import json
import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.db import models, transaction
from django.db.models import Q
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views.generic import (
    ListView, CreateView, DetailView, UpdateView,
    TemplateView, View, DeleteView,
)

# Excel
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.drawing.image import Image as XLImage

# Local imports
from .models import (
    Invoice, Expense, InvoiceItem, Quotation, QuotationItem,
    Payment, Receipt, Plan, ClientSubscription,
)
from .forms import (
    InvoiceForm, InvoiceItemForm, PaymentForm, ExpenseForm,
    QuotationForm, QuotationItemFormSet, SubscriptionChangeForm,
)
from .services import InvoiceService, QuotationService, ReceiptService
from .reports import ReportService
from .tasks import generate_invoice_pdf, generate_quotation_pdf

from core.models import SiteConfig
from core.mixins import RoleRequiredMixin
from infrastructure.pdf_service import pdf_response
from accounts.decorators import rate_limit, get_client_ip

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Brand constants for Excel
# -----------------------------------------------------------------------------
BRAND_BLUE = "2C5AA0"
BRAND_BLUE_FILL = PatternFill('solid', fgColor=BRAND_BLUE)
WHITE = "FFFFFF"
GREY_LABEL = "64748B"


# -----------------------------------------------------------------------------
# Helper: send payment reminder email
# -----------------------------------------------------------------------------
def send_payment_reminder(invoice):
    """Send an email reminder to client for an overdue or outstanding invoice."""
    try:
        from django.core.mail import send_mail
        config = SiteConfig.get()
        subject = f"Payment Reminder: {invoice.invoice_number}"
        message = (
            f"Dear {invoice.client.name},\n\n"
            f"Invoice {invoice.invoice_number} of amount "
            f"{config.currency_symbol}{invoice.balance_due} is due on "
            f"{invoice.due_date}. Please arrange payment.\n\n"
            f"Thank you for your business.\n\n"
            f"{config.company_name}"
        )
        send_mail(
            subject=subject, message=message,
            from_email=config.email or settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invoice.client.email],
            fail_silently=True,
        )
    except Exception as e:
        logger.warning(
            f"Failed to send payment reminder for "
            f"{invoice.invoice_number}: {e}"
        )


# -----------------------------------------------------------------------------
# Excel helper functions
# -----------------------------------------------------------------------------
def _setup_excel_columns(ws):
    """Set column widths matching the printable layout."""
    ws.column_dimensions['A'].width = 2
    ws.column_dimensions['B'].width = 5.5
    ws.column_dimensions['C'].width = 40
    ws.column_dimensions['D'].width = 2
    ws.column_dimensions['E'].width = 10
    ws.column_dimensions['F'].width = 16
    ws.column_dimensions['G'].width = 24
    ws.column_dimensions['H'].width = 18


def _embed_logo_topright(ws, logo_path, size_px=130, anchor='F1'):
    """Place the logo floating top-right of the sheet."""
    if not logo_path or not Path(logo_path).exists():
        logger.warning(
            f"Logo not found at {logo_path}; Excel export will have no logo."
        )
        return
    try:
        img = XLImage(str(logo_path))
        img.width = size_px
        img.height = size_px
        ws.add_image(img, anchor)
    except Exception as e:
        logger.warning(f"Could not embed logo in Excel: {e}")


def _write_excel_header(ws, config, doc_type, doc_number,
                        party_label, party_lines,
                        location_lines, date_lines):
    """Write the top header block (company, logo, parties, dates)."""
    for r in range(1, 7):
        ws.row_dimensions[r].height = 22

    ws.cell(row=3, column=2, value=f"#{doc_number}").font = Font(
        bold=True, size=10, color=BRAND_BLUE,
    )

    c = ws.cell(row=2, column=3, value=config.company_name)
    c.font = Font(bold=True, size=16, color=BRAND_BLUE)

    ws.cell(row=3, column=3, value=config.address or '').font = Font(size=9)
    ws.cell(row=4, column=3, value=config.website or '').font = Font(size=9)
    contact = " · ".join([p for p in [config.email, config.phone] if p])
    ws.cell(row=5, column=3, value=contact).font = Font(size=9)

    # Vertical doc_type label
    ws.merge_cells('B9:B13')
    vcell = ws['B9']
    vcell.value = doc_type
    vcell.font = Font(bold=True, size=20, color=BRAND_BLUE)
    vcell.alignment = Alignment(
        text_rotation=90, horizontal='center', vertical='center'
    )

    # Party block
    ws.cell(row=8, column=3, value=party_label).font = Font(
        bold=True, size=9, color=BRAND_BLUE,
    )
    for i, line in enumerate(party_lines):
        cell = ws.cell(row=9 + i, column=3, value=line)
        cell.font = Font(bold=True, size=10) if i == 0 else Font(size=9)

    # Location block
    ws.cell(row=8, column=5, value="LOCATION").font = Font(
        bold=True, size=9, color=BRAND_BLUE,
    )
    for i, line in enumerate(location_lines):
        ws.cell(row=9 + i, column=5, value=line).font = Font(size=9)

    # Dates (right aligned)
    for i, (label, value) in enumerate(date_lines):
        lbl = ws.cell(row=8 + i, column=7, value=label)
        lbl.font = Font(bold=True, size=9)
        lbl.alignment = Alignment(horizontal='right')
        val = ws.cell(row=8 + i, column=8, value=value)
        val.font = Font(size=9)


def _write_items_table(ws, items, start_row):
    """Write the items table starting at `start_row`. Returns next row index."""
    headers = [(3, "DESCRIPTION"), (5, "QTY"), (6, "UNIT PRICE"), (8, "TOTAL")]
    for col, label in headers:
        c = ws.cell(row=start_row, column=col, value=label)
        c.font = Font(bold=True, color=WHITE, size=9)
        c.fill = BRAND_BLUE_FILL
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = Border(
            bottom=Side(style='thin', color=WHITE),
            top=Side(style='thin', color=WHITE),
        )
    ws.row_dimensions[start_row].height = 22

    row = start_row + 1
    for idx, item in enumerate(items):
        ws.cell(row=row, column=3, value=str(item.description)).font = Font(size=9)
        qty = ws.cell(row=row, column=5, value=float(item.quantity))
        qty.font = Font(size=9)
        qty.alignment = Alignment(horizontal='center')
        up = ws.cell(row=row, column=6, value=float(item.unit_price))
        up.font = Font(size=9)
        up.alignment = Alignment(horizontal='right')
        tot = ws.cell(row=row, column=8, value=float(item.total))
        tot.font = Font(size=9)
        tot.alignment = Alignment(horizontal='right')

        if idx % 2 == 1:
            for col in (3, 5, 6, 8):
                ws.cell(row=row, column=col).fill = PatternFill(
                    'solid', fgColor="F8FAFC"
                )
        row += 1
    return row


def _write_totals_block(ws, start_row, subtotal, tax_amount, total_amount,
                        include_vat, vat_rate,
                        amount_paid=None, balance_due=None):
    """Write the totals block starting at `start_row`."""
    def _put(r, label, value, bold=False, highlight=False, fmt=None):
        lbl = ws.cell(row=r, column=7, value=label)
        lbl.font = Font(bold=True, size=9,
                        color=WHITE if highlight else "000000")
        lbl.alignment = Alignment(horizontal='right')
        val = ws.cell(row=r, column=8, value=value)
        val.font = Font(bold=bold, size=10 if highlight else 9,
                        color=WHITE if highlight else "000000")
        val.alignment = Alignment(horizontal='right')
        if fmt:
            val.number_format = fmt
        if highlight:
            lbl.fill = BRAND_BLUE_FILL
            val.fill = BRAND_BLUE_FILL
            ws.row_dimensions[r].height = 20

    _put(start_row, "SUBTOTAL", float(subtotal), bold=True)
    _put(start_row + 1, "DISCOUNT", 0.0)
    discount = 0.0
    _put(start_row + 2, "SUBTOTAL LESS DISCOUNT", float(subtotal) - discount)

    tax_rate = float(vat_rate) if include_vat else 0.0
    _put(start_row + 3, "TAX RATE", tax_rate, fmt='0.00%')
    _put(start_row + 4, "TOTAL TAX", float(tax_amount))

    if amount_paid is not None and float(amount_paid) > 0:
        _put(start_row + 5, "Amount Paid", float(amount_paid))
        _put(start_row + 6, "Balance Due", float(balance_due or 0.0),
             bold=True, highlight=True)
        return start_row + 6
    else:
        _put(start_row + 5, "Balance Due", float(total_amount),
             bold=True, highlight=True)
        return start_row + 5


def _write_footer(ws, start_row, config, notes=None):
    """Write thank-you + Terms & Instructions footer."""
    thank_row = start_row + 2
    ws.cell(row=thank_row, column=3,
            value="Thank you for your business!").font = Font(
        italic=True, size=9, color=GREY_LABEL,
    )

    terms_row = thank_row + 2
    ws.cell(row=terms_row, column=3,
            value="Terms & Instructions").font = Font(
        bold=True, size=9, color=BRAND_BLUE,
    )

    lines = []
    if notes:
        lines.append(str(notes.html if hasattr(notes, 'html') else notes))
    if config.bank_name:
        bank = f"Bank: {config.bank_name}"
        if config.bank_account:
            bank += f"  —  Account: {config.bank_account}"
        lines.append(bank)
    if config.mobile_money:
        lines.append(f"Mobile Money: {config.mobile_money}")
    lines.append(config.invoice_footer or "Payment is due within 30 days.")

    for i, line in enumerate(lines):
        ws.cell(row=terms_row + 1 + i, column=3,
                value=line).font = Font(size=9, color=GREY_LABEL)


# =============================================================================
# QUOTATION VIEWS (Staff only)
# =============================================================================

class QuotationListView(RoleRequiredMixin, ListView):
    model = Quotation
    template_name = 'finance/quotation_list.html'
    context_object_name = 'quotations'
    paginate_by = 20
    required_roles = ['FINANCE', 'ADMIN']

    def get_queryset(self):
        qs = super().get_queryset().select_related('client')
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

        if self.request.POST.get('action') == 'send':
            try:
                QuotationService.send(self.object)
                messages.success(self.request, 'Quotation sent to client.')
            except ValueError as e:
                messages.error(self.request, str(e))
        else:
            messages.success(self.request, 'Quotation saved as draft.')
        return redirect('quotation_detail', pk=self.object.pk)

    def form_invalid(self, form):
        messages.error(
            self.request, "Please correct errors in the quotation header."
        )
        return self.render_to_response(self.get_context_data(form=form))


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
            ctx['items'] = QuotationItemFormSet(
                self.request.POST, instance=self.object
            )
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
        if self.request.POST.get('action') == 'send':
            try:
                QuotationService.send(self.object)
                messages.success(self.request, 'Quotation sent to client.')
            except ValueError as e:
                messages.error(self.request, str(e))
        else:
            messages.success(self.request, 'Quotation updated.')
        return redirect('quotation_detail', pk=self.object.pk)

    def form_invalid(self, form):
        messages.error(
            self.request, "Please correct errors in the quotation header."
        )
        return self.render_to_response(self.get_context_data(form=form))


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
            invoice = QuotationService.convert_to_invoice(
                quotation, created_by=request.user
            )
            messages.success(
                request,
                f'Quotation converted to Invoice {invoice.invoice_number}.',
            )
            return redirect('invoice_detail', pk=invoice.pk)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('quotation_detail', pk=pk)


class DuplicateQuotationView(RoleRequiredMixin, View):
    required_roles = ['FINANCE', 'ADMIN']

    def post(self, request, pk):
        original = get_object_or_404(Quotation, pk=pk)
        new_quotation = Quotation.objects.create(
            client=original.client,
            issue_date=date.today(),
            valid_until=date.today() + timedelta(days=30),
            notes=f"Duplicated from {original.quotation_number}",
            created_by=request.user, status='draft',
            include_vat=original.include_vat,
        )
        for item in original.items.all():
            QuotationItem.objects.create(
                quotation=new_quotation, description=item.description,
                quantity=item.quantity, unit_price=item.unit_price,
                total=item.total,
            )
        QuotationService.recalculate(new_quotation)
        messages.success(
            request,
            f'Quotation duplicated as {new_quotation.quotation_number}.',
        )
        return redirect('quotation_detail', pk=new_quotation.pk)


class QuotationDeleteView(RoleRequiredMixin, DeleteView):
    model = Quotation
    success_url = reverse_lazy('quotation_list')
    template_name = 'finance/quotation_confirm_delete.html'
    required_roles = ['FINANCE', 'ADMIN']

    def get_queryset(self):
        return super().get_queryset().filter(status='draft')

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(
            request,
            f"Quotation {obj.quotation_number} has been deleted.",
        )
        return super().delete(request, *args, **kwargs)


# -----------------------------------------------------------------------------
# Quotation export views
# -----------------------------------------------------------------------------

def quotation_print_view(request, pk):
    """Browser-printable quotation."""
    quotation = get_object_or_404(Quotation, pk=pk)
    return TemplateResponse(request, 'finance/quotation_print.html', {
        'quotation': quotation,
        'items': quotation.items.all(),
        'site_config': SiteConfig.get(),
        'config': SiteConfig.get(),
    })


def quotation_pdf_direct(request, pk):
    """Generate the quotation PDF synchronously via ReportLab."""
    from infrastructure.pdf_reportlab import (
        render_quotation_pdf, load_logo_data_uri,
    )
    quotation = get_object_or_404(Quotation, pk=pk)
    config = SiteConfig.get()
    logo_data_uri = load_logo_data_uri()
    try:
        pdf_bytes = render_quotation_pdf(quotation, config, logo_data_uri)
    except Exception as e:
        logger.exception(
            f"ReportLab failed for quotation "
            f"{quotation.quotation_number}: {e}"
        )
        messages.error(request, "Failed to generate PDF. Please try again.")
        return redirect('quotation_detail', pk=pk)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="quotation_{quotation.quotation_number}.pdf"'
    )
    return response


def invoice_pdf_direct(request, pk):
    """Generate the invoice PDF synchronously via ReportLab."""
    from infrastructure.pdf_reportlab import (
        render_invoice_pdf, load_logo_data_uri,
    )
    invoice = get_object_or_404(Invoice, pk=pk)
    config = SiteConfig.get()
    logo_data_uri = load_logo_data_uri()
    try:
        pdf_bytes = render_invoice_pdf(invoice, config, logo_data_uri)
    except Exception as e:
        logger.exception(
            f"ReportLab failed for invoice {invoice.invoice_number}: {e}"
        )
        messages.error(request, "Failed to generate PDF. Please try again.")
        return redirect('invoice_detail', pk=pk)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
    )
    return response


def quotation_word_export(request, pk):
    """Download the quotation as a .doc file (HTML wrapped)."""
    quotation = get_object_or_404(Quotation, pk=pk)
    response = HttpResponse(content_type='application/msword')
    response['Content-Disposition'] = (
        f'attachment; filename="quotation_{quotation.quotation_number}.doc"'
    )
    template = render_to_string('finance/quotation_print.html', {
        'quotation': quotation,
        'items': quotation.items.all(),
        'site_config': SiteConfig.get(),
        'config': SiteConfig.get(),
    })
    response.write(template)
    return response


def quotation_excel_export(request, pk):
    """Export quotation as Excel (.xlsx) matching the printable template."""
    quotation = get_object_or_404(Quotation, pk=pk)
    items = list(quotation.items.all())
    config = SiteConfig.get()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Quotation"

    _setup_excel_columns(ws)

    logo_path = Path(settings.BASE_DIR) / 'static' / 'images' / 'logo.png'
    _embed_logo_topright(ws, logo_path, size_px=130, anchor='F1')

    party_lines = [
        quotation.client.name,
        quotation.client.address or '',
        ", ".join([
            p for p in [quotation.client.email, quotation.client.phone] if p
        ]),
    ]
    location_lines = [config.company_name, config.address or '', config.phone or '']
    date_lines = [
        ("Issue Date:", quotation.issue_date.strftime('%d/%m/%Y')),
        ("Valid Until:", quotation.valid_until.strftime('%d/%m/%Y')),
    ]
    _write_excel_header(
        ws, config, "QUOTATION", quotation.quotation_number,
        "BILL TO", party_lines, location_lines, date_lines,
    )

    row_after_items = _write_items_table(ws, items, start_row=14)

    _write_totals_block(
        ws, start_row=row_after_items + 1,
        subtotal=quotation.subtotal,
        tax_amount=quotation.tax_amount,
        total_amount=quotation.total_amount,
        include_vat=quotation.include_vat,
        vat_rate=config.vat_rate,
    )

    _write_footer(
        ws, start_row=row_after_items + 8,
        config=config, notes=quotation.notes,
    )

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = (
        f'attachment; filename="quotation_{quotation.quotation_number}.xlsx"'
    )
    wb.save(response)
    return response


def invoice_excel_export(request, pk):
    """Export invoice as Excel (.xlsx) matching the printable template."""
    invoice = get_object_or_404(Invoice, pk=pk)
    items = list(invoice.items.all())
    config = SiteConfig.get()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Invoice"

    _setup_excel_columns(ws)

    logo_path = Path(settings.BASE_DIR) / 'static' / 'images' / 'logo.png'
    _embed_logo_topright(ws, logo_path, size_px=130, anchor='F1')

    party_lines = [
        invoice.client.name,
        invoice.client.address or '',
        ", ".join([
            p for p in [invoice.client.email, invoice.client.phone] if p
        ]),
    ]
    location_lines = [config.company_name, config.address or '', config.phone or '']
    date_lines = [
        ("Invoice Date:", invoice.issue_date.strftime('%d/%m/%Y')),
        ("Due Date:", invoice.due_date.strftime('%d/%m/%Y')),
    ]
    _write_excel_header(
        ws, config, "INVOICE", invoice.invoice_number,
        "BILL TO", party_lines, location_lines, date_lines,
    )

    row_after_items = _write_items_table(ws, items, start_row=14)

    _write_totals_block(
        ws, start_row=row_after_items + 1,
        subtotal=invoice.subtotal,
        tax_amount=invoice.tax_amount,
        total_amount=invoice.total_amount,
        include_vat=invoice.include_vat,
        vat_rate=config.vat_rate,
        amount_paid=invoice.amount_paid,
        balance_due=invoice.balance_due,
    )

    _write_footer(
        ws, start_row=row_after_items + 10,
        config=config, notes=invoice.notes,
    )

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = (
        f'attachment; filename="invoice_{invoice.invoice_number}.xlsx"'
    )
    wb.save(response)
    return response


@method_decorator(
    rate_limit(key_func=get_client_ip, rate='30/h', method='GET', block=True),
    name='dispatch',
)
class QuotationPDFView(RoleRequiredMixin, View):
    required_roles = ['FINANCE', 'ADMIN']

    def get(self, request, pk):
        cache_key = f'quotation_pdf_{pk}'
        pdf_bytes = cache.get(cache_key)
        if pdf_bytes:
            return pdf_response(pdf_bytes, f'Quotation_{pk}.pdf')
        generate_quotation_pdf.delay(pk)
        return HttpResponse(
            'PDF is being generated. Please refresh in a few moments.',
            status=202, content_type='text/plain',
        )


# =============================================================================
# INVOICE VIEWS (Staff only)
# =============================================================================

class InvoiceListView(RoleRequiredMixin, ListView):
    model = Invoice
    template_name = 'finance/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20
    required_roles = ['FINANCE', 'ADMIN']

    def get_queryset(self):
        qs = super().get_queryset().select_related('client')
        for param, lookup in [
            ('status', 'status'),
            ('issue_from', 'issue_date__gte'),
            ('issue_to', 'issue_date__lte'),
            ('due_from', 'due_date__gte'),
            ('due_to', 'due_date__lte'),
        ]:
            val = self.request.GET.get(param)
            if val:
                qs = qs.filter(**{lookup: val})
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Invoice.STATUS_CHOICES
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['issue_from'] = self.request.GET.get('issue_from', '')
        ctx['issue_to'] = self.request.GET.get('issue_to', '')
        ctx['due_from'] = self.request.GET.get('due_from', '')
        ctx['due_to'] = self.request.GET.get('due_to', '')
        qs = self.get_queryset()
        ctx['total_amount_sum'] = (
            qs.aggregate(total=models.Sum('total_amount'))['total'] or 0
        )
        ctx['total_paid_sum'] = (
            qs.aggregate(total=models.Sum('amount_paid'))['total'] or 0
        )
        ctx['total_balance_sum'] = (
            ctx['total_amount_sum'] - ctx['total_paid_sum']
        )
        return ctx


class InvoiceCreateView(RoleRequiredMixin, CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'finance/invoice_form.html'
    required_roles = ['FINANCE', 'ADMIN']

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(
            self.request,
            'Invoice created. You can now add line items.',
        )
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
        # Receipt (if paid)
        ctx['receipt'] = getattr(self.object, 'receipt', None)
        ctx['config'] = SiteConfig.get()
        return ctx


class AddInvoiceItemView(RoleRequiredMixin, View):
    required_roles = ['FINANCE', 'ADMIN']

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        if invoice.status != 'draft':
            messages.error(
                request, 'Items can only be added to draft invoices.'
            )
            return redirect('invoice_detail', pk=pk)
        form = InvoiceItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.invoice = invoice
            item.save()
            InvoiceService.recalculate(invoice)
            messages.success(request, 'Item added.')
        else:
            messages.error(request, 'Invalid item data.')
        return redirect('invoice_detail', pk=pk)


class RecordPaymentView(RoleRequiredMixin, View):
    """
    Record a payment against an invoice.

    If the payment fully settles the invoice, a Receipt is auto-created by
    InvoiceService.record_payment(). Optional transaction metadata
    (transaction_id, fee, source/destination accounts, payment_datetime)
    is read from POST fields when present.
    """
    required_roles = ['FINANCE', 'ADMIN']

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)

        lock_key = f"payment_lock_{invoice.pk}_{request.user.pk}"
        if cache.get(lock_key):
            messages.error(
                request,
                "You are recording payments too quickly. Please wait a moment.",
            )
            return redirect('invoice_detail', pk=pk)

        form = PaymentForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Invalid payment data.')
            return redirect('invoice_detail', pk=pk)

        amount = form.cleaned_data['amount']
        if amount > invoice.balance_due:
            messages.error(
                request,
                f"Payment amount cannot exceed the outstanding balance "
                f"({invoice.balance_due}).",
            )
            return redirect('invoice_detail', pk=pk)

        cache.set(lock_key, True, timeout=5)

        # Optional transaction metadata
        try:
            transaction_fee = Decimal(request.POST.get('transaction_fee') or '0')
        except (InvalidOperation, ValueError):
            transaction_fee = Decimal('0')

        payment_datetime = None
        raw_dt = (request.POST.get('payment_datetime') or '').strip()
        if raw_dt:
            try:
                parsed = parse_datetime(raw_dt)
                if parsed and timezone.is_naive(parsed):
                    parsed = timezone.make_aware(
                        parsed, timezone.get_current_timezone()
                    )
                payment_datetime = parsed
            except (ValueError, TypeError):
                payment_datetime = None

        InvoiceService.record_payment(
            invoice=invoice,
            recorded_by=request.user,
            transaction_id=(request.POST.get('transaction_id') or '').strip(),
            transaction_fee=transaction_fee,
            source_account=(request.POST.get('source_account') or '').strip(),
            destination_account=(
                request.POST.get('destination_account') or ''
            ).strip(),
            payment_datetime=payment_datetime,
            **form.cleaned_data,
        )
        messages.success(request, 'Payment recorded.')

        # If the invoice became fully paid, surface the auto-receipt
        invoice.refresh_from_db()
        receipt = getattr(invoice, 'receipt', None)
        if receipt:
            messages.success(
                request,
                f"Receipt {receipt.receipt_number} was issued automatically.",
            )

        return redirect('invoice_detail', pk=pk)


class IssueInvoiceView(RoleRequiredMixin, View):
    required_roles = ['FINANCE', 'ADMIN']

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        try:
            InvoiceService.issue(invoice)
            messages.success(
                request, f'Invoice {invoice.invoice_number} issued.'
            )
        except ValueError as e:
            messages.error(request, str(e))
        return redirect('invoice_detail', pk=pk)


class BulkInvoiceActionView(RoleRequiredMixin, View):
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
            messages.success(
                request, f'Reminder sent to {len(invoices)} client(s).'
            )
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
    required_roles = ['FINANCE', 'ADMIN']

    def get(self, request):
        qs = Invoice.objects.select_related('client')
        for param, lookup in [
            ('status', 'status'),
            ('issue_from', 'issue_date__gte'),
            ('issue_to', 'issue_date__lte'),
            ('due_from', 'due_date__gte'),
            ('due_to', 'due_date__lte'),
        ]:
            val = request.GET.get(param)
            if val:
                qs = qs.filter(**{lookup: val})
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="invoices.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Invoice #', 'Client', 'Issue Date', 'Due Date',
            'Total', 'Paid', 'Balance', 'Status',
        ])
        for inv in qs:
            writer.writerow([
                inv.invoice_number, inv.client.name,
                inv.issue_date, inv.due_date,
                inv.total_amount, inv.amount_paid,
                inv.balance_due, inv.get_status_display(),
            ])
        return response


@method_decorator(
    rate_limit(key_func=get_client_ip, rate='30/h', method='GET', block=True),
    name='dispatch',
)
class InvoicePDFView(RoleRequiredMixin, View):
    required_roles = ['FINANCE', 'ADMIN']

    def get(self, request, pk):
        cache_key = f'invoice_pdf_{pk}'
        pdf_bytes = cache.get(cache_key)
        if pdf_bytes:
            return pdf_response(pdf_bytes, f'Invoice_{pk}.pdf')
        generate_invoice_pdf.delay(pk)
        return HttpResponse(
            'PDF is being generated. Please refresh in a few moments.',
            status=202, content_type='text/plain',
        )


# =============================================================================
# RECEIPT VIEWS
# =============================================================================

class ReceiptListView(RoleRequiredMixin, ListView):
    """Finance/admin list of all receipts."""
    model = Receipt
    template_name = 'finance/receipt_list.html'
    context_object_name = 'receipts'
    paginate_by = 20
    required_roles = ['FINANCE', 'ADMIN']

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            'payment', 'invoice', 'invoice__client'
        )
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(receipt_number__icontains=q)
                | Q(invoice__invoice_number__icontains=q)
                | Q(invoice__client__name__icontains=q)
            )
        return qs


class ReceiptDetailView(RoleRequiredMixin, DetailView):
    """Printable/viewable receipt detail for staff."""
    model = Receipt
    template_name = 'finance/receipt_detail.html'
    context_object_name = 'receipt'
    required_roles = ['FINANCE', 'ADMIN']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['config'] = SiteConfig.get()
        ctx['payment'] = self.object.payment
        ctx['invoice'] = self.object.invoice
        ctx['items'] = self.object.invoice.items.all()
        return ctx


def receipt_pdf_direct(request, pk):
    """Synchronous PDF download for a receipt."""
    from infrastructure.pdf_reportlab import (
        render_receipt_pdf, load_logo_data_uri,
    )
    receipt = get_object_or_404(Receipt, pk=pk)
    config = SiteConfig.get()
    logo_data_uri = load_logo_data_uri()
    try:
        pdf_bytes = render_receipt_pdf(receipt, config, logo_data_uri)
    except Exception as e:
        logger.exception(
            f"ReportLab failed for receipt {receipt.receipt_number}: {e}"
        )
        messages.error(request, "Failed to generate receipt PDF. Please try again.")
        return redirect('receipt_detail', pk=pk)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="receipt_{receipt.receipt_number}.pdf"'
    )
    return response


# =============================================================================
# EXPENSE VIEWS
# =============================================================================

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


class ApproveExpenseView(RoleRequiredMixin, View):
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
        messages.success(
            request, f'Expense "{expense.description}" approved.'
        )
        return redirect('expense_list')


class RejectExpenseView(RoleRequiredMixin, View):
    required_roles = ['FINANCE', 'ADMIN']

    def post(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        if expense.status != 'pending':
            messages.error(request, 'This expense is already processed.')
            return redirect('expense_list')
        expense.status = 'rejected'
        expense.save()
        messages.warning(
            request, f'Expense "{expense.description}" rejected.'
        )
        return redirect('expense_list')


# =============================================================================
# FINANCIAL REPORTS
# =============================================================================

class ReportView(RoleRequiredMixin, TemplateView):
    template_name = 'finance/reports.html'
    required_roles = ['FINANCE', 'ADMIN']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        period = self.request.GET.get('period', 'this_month')
        start, end = ReportService.date_range(period)
        ctx.update({
            'period': period,
            'start': start,
            'end': end,
            'income': ReportService.income_statement(start, end),
            'aging': ReportService.accounts_receivable_aging(),
            'top_clients': ReportService.client_revenue(start, end),
            'monthly': ReportService.monthly_revenue(6),
            'monthly_json': json.dumps(ReportService.monthly_revenue(6)),
            'config': SiteConfig.get(),
            'period_choices': [
                ('this_month', 'This Month'), ('last_month', 'Last Month'),
                ('last_30', 'Last 30 Days'), ('last_90', 'Last 90 Days'),
                ('this_quarter', 'This Quarter'), ('this_year', 'This Year'),
            ],
        })
        try:
            ctx['service_revenue'] = ReportService.service_revenue(start, end)
            ctx['most_requested_services'] = (
                ReportService.most_requested_services()
            )
            ctx['technician_performance'] = (
                ReportService.technician_performance()
            )
        except Exception as e:
            ctx.update({
                'service_revenue': [],
                'most_requested_services': [],
                'technician_performance': [],
            })
            logger.warning(f"Could not load service analytics: {e}")
        return ctx


# =============================================================================
# CLIENT-FACING VIEWS
# =============================================================================

class ClientInvoiceListView(LoginRequiredMixin, ListView):
    template_name = 'finance/client_invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20

    def get_queryset(self):
        client_org = getattr(self.request.user, 'client_organization', None)
        if not client_org:
            return Invoice.objects.none()
        return Invoice.objects.filter(
            client=client_org
        ).order_by('-created_at')


class ClientInvoiceDetailView(LoginRequiredMixin, DetailView):
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
        ctx['receipt'] = getattr(self.object, 'receipt', None)
        return ctx


class ClientQuotationListView(LoginRequiredMixin, ListView):
    template_name = 'finance/client_quotation_list.html'
    context_object_name = 'quotations'
    paginate_by = 20

    def get_queryset(self):
        client_org = getattr(self.request.user, 'client_organization', None)
        if not client_org:
            return Quotation.objects.none()
        return Quotation.objects.filter(
            client=client_org
        ).order_by('-created_at')


class ClientQuotationDetailView(LoginRequiredMixin, DetailView):
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
    def post(self, request, pk):
        quotation = get_object_or_404(
            Quotation, pk=pk,
            client=request.user.client_organization,
        )
        if quotation.status != 'sent':
            messages.error(
                request,
                f"This quotation cannot be approved "
                f"(current status: {quotation.status}).",
            )
            return redirect('client_quotation_detail', pk=pk)
        quotation.status = 'approved'
        quotation.save(update_fields=['status'])
        try:
            invoice = QuotationService.convert_to_invoice(
                quotation, created_by=request.user
            )
            messages.success(
                request,
                f"Quotation {quotation.quotation_number} approved and "
                f"converted to invoice {invoice.invoice_number}.",
            )
            return redirect('client_invoice_detail', pk=invoice.pk)
        except ValueError as e:
            messages.error(request, f"Conversion failed: {e}")
            quotation.status = 'sent'
            quotation.save(update_fields=['status'])
            return redirect('client_quotation_detail', pk=pk)


class ClientQuotationRejectView(LoginRequiredMixin, View):
    def post(self, request, pk):
        quotation = get_object_or_404(
            Quotation, pk=pk,
            client=request.user.client_organization,
        )
        if quotation.status != 'sent':
            messages.error(request, "This quotation cannot be rejected.")
            return redirect('client_quotation_detail', pk=pk)
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(
                request,
                "Please provide a reason for rejection or change request.",
            )
            return redirect('client_quotation_detail', pk=pk)
        quotation.status = 'rejected'
        quotation.client_feedback = reason
        quotation.save(update_fields=['status', 'client_feedback'])

        try:
            from django.core.mail import send_mail
            config = SiteConfig.get()
            send_mail(
                subject=(
                    f"Quotation {quotation.quotation_number} rejected by "
                    f"{quotation.client.name}"
                ),
                message=f"Client feedback:\n{reason}",
                from_email=config.email or settings.DEFAULT_FROM_EMAIL,
                recipient_list=['finance@pritech.mw'],
                fail_silently=True,
            )
        except Exception:
            pass

        messages.success(
            request,
            "Quotation rejected. We'll review your feedback and get back to you.",
        )
        return redirect('client_quotation_detail', pk=pk)


# ---- Client Receipts --------------------------------------------------------

class ClientReceiptListView(LoginRequiredMixin, ListView):
    """Client's list of receipts (their payment history)."""
    template_name = 'finance/client_receipt_list.html'
    context_object_name = 'receipts'
    paginate_by = 20

    def get_queryset(self):
        org = getattr(self.request.user, 'client_organization', None)
        if not org:
            return Receipt.objects.none()
        return Receipt.objects.filter(
            invoice__client=org
        ).select_related('invoice', 'payment').order_by('-issued_at')


class ClientReceiptDetailView(LoginRequiredMixin, DetailView):
    """Client's view of a single receipt."""
    template_name = 'finance/client_receipt_detail.html'
    context_object_name = 'receipt'

    def get_queryset(self):
        org = getattr(self.request.user, 'client_organization', None)
        if not org:
            return Receipt.objects.none()
        return Receipt.objects.filter(invoice__client=org)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['config'] = SiteConfig.get()
        ctx['payment'] = self.object.payment
        ctx['invoice'] = self.object.invoice
        ctx['items'] = self.object.invoice.items.all()
        return ctx


# ---- Client Subscriptions --------------------------------------------------

class ClientSubscriptionDetailView(LoginRequiredMixin, DetailView):
    template_name = 'finance/client_subscription_detail.html'
    context_object_name = 'subscription'

    def get_object(self, queryset=None):
        client_org = getattr(self.request.user, 'client_organization', None)
        if not client_org:
            raise Http404("No subscription found for your organization.")
        return get_object_or_404(ClientSubscription, client=client_org)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['available_plans'] = Plan.objects.filter(
            is_active=True
        ).exclude(pk=self.object.plan.pk)
        return ctx


class ClientSubscriptionUpgradeView(LoginRequiredMixin, UpdateView):
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
            subscription.plan = new_plan
            subscription.save()
            messages.success(
                self.request, f"Plan upgraded to {new_plan.name}."
            )
        else:
            subscription.cancel_at_period_end = True
            subscription.save()
            messages.info(
                self.request,
                f"Plan will downgrade to {new_plan.name} at the end of current period.",
            )
        return redirect(self.success_url)


class ClientSubscriptionCancelView(LoginRequiredMixin, View):
    def post(self, request):
        client_org = getattr(request.user, 'client_organization', None)
        if not client_org:
            messages.error(request, "No active subscription found.")
            return redirect('client_subscription_detail')
        subscription = get_object_or_404(
            ClientSubscription, client=client_org
        )
        subscription.cancel_at_period_end = True
        subscription.save()
        messages.warning(
            request,
            "Your subscription will be cancelled at the end of the current billing period.",
        )
        return redirect('client_subscription_detail')


# =============================================================================
# HTMX REAL-TIME ENDPOINTS
# =============================================================================

def live_quotation_search(request):
    query = request.GET.get('q', '')
    status = request.GET.get('status', '')
    quotations = Quotation.objects.select_related('client').all()
    if query:
        quotations = quotations.filter(
            Q(quotation_number__icontains=query)
            | Q(client__name__icontains=query)
        )
    if status:
        quotations = quotations.filter(status=status)
    html = render_to_string('finance/partials/quotation_rows.html', {
        'quotations': quotations,
        'site_config': SiteConfig.get(),
    })
    return HttpResponse(html)


def update_quotation_status(request, pk):
    quotation = get_object_or_404(Quotation, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in ['draft', 'sent'] and quotation.status != 'converted':
            quotation.status = new_status
            quotation.save()
            if new_status == 'sent':
                QuotationService.send(quotation)
    badge_map = {
        'draft': 'secondary', 'sent': 'primary', 'approved': 'success',
        'converted': 'secondary', 'rejected': 'danger', 'expired': 'warning',
    }
    badge_class = badge_map.get(quotation.status, 'secondary')
    return HttpResponse(
        f'<span class="badge bg-{badge_class}">'
        f'{quotation.get_status_display()}</span>'
    )


def live_invoice_search(request):
    query = request.GET.get('q', '')
    status = request.GET.get('status', '')
    invoices = Invoice.objects.select_related('client').all()
    if query:
        invoices = invoices.filter(
            Q(invoice_number__icontains=query)
            | Q(client__name__icontains=query)
        )
    if status:
        invoices = invoices.filter(status=status)
    html = render_to_string('finance/partials/invoice_rows.html', {
        'invoices': invoices,
        'site_config': SiteConfig.get(),
    })
    return HttpResponse(html)