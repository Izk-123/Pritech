# infrastructure/pdf_reportlab.py
"""
ReportLab-based PDF generator for Invoices and Quotations.
Matches the modern vertical-label design used across the platform.

Public API:
    render_invoice_pdf(invoice, config, logo_data_uri=None) -> bytes
    render_quotation_pdf(quotation, config, logo_data_uri=None) -> bytes
    load_logo_data_uri(path=None) -> str | None
"""

import base64
import io
import logging
import re
from pathlib import Path

from django.conf import settings

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle, Image,
)
from reportlab.graphics.shapes import Drawing, Circle, String

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Brand palette
# ---------------------------------------------------------------------------
BLUE = colors.HexColor('#2c5aa0')
DARK = colors.HexColor('#1e293b')
GREY = colors.HexColor('#475569')
LIGHT_GREY = colors.HexColor('#cbd5e1')
ROW_ALT = colors.HexColor('#f8fafc')
PLACEHOLDER_BG = colors.HexColor('#e2e8f0')
AMBER_BG = colors.HexColor('#fffbeb')
AMBER_BORDER = colors.HexColor('#fde68a')
AMBER_TEXT = colors.HexColor('#78350f')


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
def _s(name, **kw):
    base = dict(fontName='Helvetica', fontSize=9.5, textColor=DARK, leading=12)
    base.update(kw)
    return ParagraphStyle(name, **base)


STYLE_COMPANY      = _s('Company',     fontName='Helvetica-Bold', fontSize=15, textColor=BLUE, leading=18)
STYLE_COMPANY_SUB  = _s('CompanySub',  fontSize=8.5, textColor=GREY, leading=11)
STYLE_LABEL        = _s('Label',       fontName='Helvetica-Bold', fontSize=8,  textColor=BLUE, leading=10)
STYLE_PARTY_NAME   = _s('PartyName',   fontName='Helvetica-Bold', fontSize=10, leading=13)
STYLE_PARTY_DETAIL = _s('PartyDetail', fontSize=8.5, textColor=GREY, leading=11)
STYLE_DATE         = _s('Date',        fontSize=9, leading=12)
STYLE_TH           = _s('TH',          fontName='Helvetica-Bold', fontSize=8, textColor=colors.white, leading=10)
STYLE_TH_R         = _s('THR',         fontName='Helvetica-Bold', fontSize=8, textColor=colors.white, leading=10, alignment=TA_RIGHT)
STYLE_TD           = _s('TD',          fontSize=9, leading=11)
STYLE_TD_R         = _s('TDR',         fontSize=9, leading=11, alignment=TA_RIGHT)
STYLE_TOT_LBL      = _s('TotLbl',      fontSize=9, textColor=GREY, leading=12)
STYLE_TOT_VAL      = _s('TotVal',      fontName='Helvetica-Bold', fontSize=9, leading=12, alignment=TA_RIGHT)
STYLE_GRAND_LBL    = _s('GrandLbl',    fontName='Helvetica-Bold', fontSize=10, textColor=colors.white, leading=13)
STYLE_GRAND_VAL    = _s('GrandVal',    fontName='Helvetica-Bold', fontSize=10, textColor=colors.white, leading=13, alignment=TA_RIGHT)
STYLE_THANK        = _s('Thank',       fontName='Helvetica-Oblique', fontSize=9, textColor=GREY, leading=12)
STYLE_TERMS_H      = _s('TermsH',      fontName='Helvetica-Bold', fontSize=8.5, textColor=BLUE, leading=11)
STYLE_TERMS        = _s('Terms',       fontSize=8, textColor=GREY, leading=11)
STYLE_VALIDITY     = _s('Validity',    fontSize=8.5, textColor=AMBER_TEXT, leading=11, alignment=TA_CENTER)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_logo_data_uri(path=None):
    """Return the site logo as a base64 data URI, or None if not found."""
    if path is None:
        path = Path(settings.BASE_DIR) / 'static' / 'images' / 'logo.png'
    path = Path(path)
    if not path.exists():
        return None
    try:
        with open(path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')
        ext = path.suffix.lstrip('.').lower() or 'png'
        return f"data:image/{ext};base64,{b64}"
    except Exception as e:
        logger.warning(f"Could not read logo file {path}: {e}")
        return None


def _logo_flowable(logo_data_uri, size=3.4 * cm):
    """Return the logo as an Image or a circular placeholder Drawing."""
    if logo_data_uri and isinstance(logo_data_uri, str) and logo_data_uri.startswith('data:image'):
        try:
            _, b64 = logo_data_uri.split(',', 1)
            img = Image(io.BytesIO(base64.b64decode(b64)))
            ratio = size / max(img.imageWidth, img.imageHeight)
            img.drawWidth = img.imageWidth * ratio
            img.drawHeight = img.imageHeight * ratio
            img.hAlign = 'RIGHT'
            return img
        except Exception as e:
            logger.warning(f"Could not render logo image: {e}")

    d = Drawing(size, size)
    d.add(Circle(size / 2, size / 2, size / 2 - 1,
                 fillColor=PLACEHOLDER_BG, strokeColor=LIGHT_GREY))
    d.add(String(size / 2, size / 2 - 4, "LOGO",
                 textAnchor='middle',
                 fontName='Helvetica-Bold',
                 fontSize=14,
                 fillColor=colors.HexColor('#64748b')))
    d.hAlign = 'RIGHT'
    return d


def _fmt_money(symbol, value):
    try:
        return f"{symbol} {float(value):,.2f}"
    except Exception:
        return f"{symbol} {value}"


def _strip_html(text):
    if text is None:
        return ''
    if hasattr(text, 'html'):
        text = text.html
    return re.sub(r'<[^>]+>', ' ', str(text)).strip()


# ---------------------------------------------------------------------------
# DocTemplate with vertical label on the left
# ---------------------------------------------------------------------------
class _VerticalLabelDoc(BaseDocTemplate):
    """A4 document with a rotated label on the left margin."""

    def __init__(self, buffer, doc_type, doc_number, **kwargs):
        super().__init__(buffer, pagesize=A4,
                         leftMargin=0, rightMargin=0,
                         topMargin=0, bottomMargin=0,
                         **kwargs)
        self.doc_type = doc_type
        self.doc_number = doc_number

        left = 3.2 * cm
        right = 1.4 * cm
        top = 1.4 * cm
        bottom = 1.4 * cm
        frame = Frame(
            left, bottom,
            self.pagesize[0] - left - right,
            self.pagesize[1] - top - bottom,
            id='main', showBoundary=0,
            leftPadding=0, rightPadding=0,
            topPadding=0, bottomPadding=0,
        )
        self.addPageTemplates([PageTemplate(id='main', frames=[frame], onPage=self._draw_label)])

    def _draw_label(self, canvas, doc):
        # Vertical text
        canvas.saveState()
        x = 1.7 * cm
        y = self.pagesize[1] - 1.6 * cm
        canvas.translate(x, y)
        canvas.rotate(-90)

        canvas.setFillColor(BLUE)
        canvas.setFont('Helvetica-Bold', 26)
        canvas.drawString(0, 0, self.doc_type)

        tw = canvas.stringWidth(self.doc_type, 'Helvetica-Bold', 26)
        canvas.setFillColor(DARK)
        canvas.setFont('Helvetica-Bold', 11)
        canvas.drawString(tw + 10, 1, f"#{self.doc_number}")
        canvas.restoreState()

        # Divider line
        canvas.saveState()
        canvas.setStrokeColor(LIGHT_GREY)
        canvas.setLineWidth(0.5)
        canvas.line(2.6 * cm, 1.4 * cm, 2.6 * cm, self.pagesize[1] - 1.4 * cm)
        canvas.restoreState()


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------
def _header_table(config, logo_data_uri):
    lines = [Paragraph(config.company_name, STYLE_COMPANY)]
    if config.address:
        lines.append(Paragraph(config.address.replace('\n', '<br/>'), STYLE_COMPANY_SUB))
    if getattr(config, 'website', None):
        lines.append(Paragraph(config.website, STYLE_COMPANY_SUB))
    contact = []
    if config.email:
        contact.append(config.email)
    if config.phone:
        contact.append(config.phone)
    if contact:
        lines.append(Paragraph(' · '.join(contact), STYLE_COMPANY_SUB))

    tbl = Table([[lines, [_logo_flowable(logo_data_uri)]]],
                colWidths=[11.4 * cm, 4.6 * cm])
    tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return tbl


def _parties_table(config, client, d1_label, d1_val, d2_label, d2_val,
                   bill_to_label="Bill To"):
    col1 = [
        Paragraph(bill_to_label, STYLE_LABEL),
        Paragraph(client.name, STYLE_PARTY_NAME),
    ]
    detail = []
    if getattr(client, 'address', None):
        detail.append(str(client.address).replace('\n', '<br/>'))
    if getattr(client, 'email', None):
        detail.append(client.email)
    if getattr(client, 'phone', None):
        detail.append(client.phone)
    if detail:
        col1.append(Paragraph('<br/>'.join(detail), STYLE_PARTY_DETAIL))

    col2 = [Paragraph("Location", STYLE_LABEL)]
    loc_lines = [config.company_name]
    if config.address:
        loc_lines.append(str(config.address).replace('\n', '<br/>'))
    if config.phone:
        loc_lines.append(config.phone)
    col2.append(Paragraph('<br/>'.join(loc_lines), STYLE_PARTY_DETAIL))

    col3 = [
        Paragraph(f"<b>{d1_label}:</b> {d1_val}", STYLE_DATE),
        Paragraph(f"<b>{d2_label}:</b> {d2_val}", STYLE_DATE),
    ]

    tbl = Table([[col1, col2, col3]], colWidths=[7.2 * cm, 4.8 * cm, 4 * cm])
    tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LINEABOVE', (0, 0), (-1, 0), 0.5, LIGHT_GREY),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, LIGHT_GREY),
    ]))
    return tbl


def _items_table(items, currency_symbol):
    header = [
        Paragraph('Description', STYLE_TH),
        Paragraph('Qty',         STYLE_TH_R),
        Paragraph('Unit Price',  STYLE_TH_R),
        Paragraph('Total',       STYLE_TH_R),
    ]
    rows = [header]
    for item in items:
        rows.append([
            Paragraph(str(item.description), STYLE_TD),
            Paragraph(str(item.quantity),    STYLE_TD_R),
            Paragraph(_fmt_money(currency_symbol, item.unit_price), STYLE_TD_R),
            Paragraph(_fmt_money(currency_symbol, item.total),      STYLE_TD_R),
        ])

    tbl = Table(rows, colWidths=[9 * cm, 1.5 * cm, 2.8 * cm, 2.7 * cm],
                repeatRows=1)
    style = [
        ('BACKGROUND',   (0, 0), (-1, 0), BLUE),
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING',   (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 7),
        ('LINEBELOW',    (0, 1), (-1, -1), 0.25, LIGHT_GREY),
    ]
    for i in range(1, len(rows)):
        if i % 2 == 0:
            style.append(('BACKGROUND', (0, i), (-1, i), ROW_ALT))
    tbl.setStyle(TableStyle(style))
    return tbl


def _totals_table(currency_symbol, subtotal, tax_amount, total_amount,
                  include_vat, vat_percent,
                  amount_paid=None, balance_due=None):
    rows = [[
        Paragraph('Subtotal', STYLE_TOT_LBL),
        Paragraph(_fmt_money(currency_symbol, subtotal), STYLE_TOT_VAL),
    ]]
    if include_vat:
        rows.append([
            Paragraph('Tax Rate (VAT)', STYLE_TOT_LBL),
            Paragraph(f'{vat_percent}%', STYLE_TOT_VAL),
        ])
        rows.append([
            Paragraph('Total Tax', STYLE_TOT_LBL),
            Paragraph(_fmt_money(currency_symbol, tax_amount), STYLE_TOT_VAL),
        ])

    grand_idx = len(rows)
    rows.append([
        Paragraph('Total', STYLE_GRAND_LBL),
        Paragraph(_fmt_money(currency_symbol, total_amount), STYLE_GRAND_VAL),
    ])

    balance_idx = None
    if amount_paid is not None and float(amount_paid) > 0:
        rows.append([
            Paragraph('Amount Paid', STYLE_TOT_LBL),
            Paragraph(_fmt_money(currency_symbol, amount_paid), STYLE_TOT_VAL),
        ])
        balance_idx = len(rows)
        rows.append([
            Paragraph('Balance Due', STYLE_GRAND_LBL),
            Paragraph(_fmt_money(currency_symbol, balance_due), STYLE_GRAND_VAL),
        ])

    tbl = Table(rows, colWidths=[4.2 * cm, 3.4 * cm])
    style = [
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING',   (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 4),
        ('BACKGROUND',   (0, grand_idx), (-1, grand_idx), BLUE),
        ('TOPPADDING',   (0, grand_idx), (-1, grand_idx), 8),
        ('BOTTOMPADDING',(0, grand_idx), (-1, grand_idx), 8),
    ]
    if balance_idx is not None:
        style += [
            ('BACKGROUND',   (0, balance_idx), (-1, balance_idx), BLUE),
            ('TOPPADDING',   (0, balance_idx), (-1, balance_idx), 8),
            ('BOTTOMPADDING',(0, balance_idx), (-1, balance_idx), 8),
        ]
    tbl.setStyle(TableStyle(style))
    return tbl


def _terms_table(config, notes=None):
    rows = [[Paragraph('Terms & Instructions', STYLE_TERMS_H)]]
    note_text = _strip_html(notes) if notes else ''
    if note_text:
        rows.append([Paragraph(note_text, STYLE_TERMS)])
        rows.append([Spacer(1, 4)])

    if config.bank_name:
        line = f"Bank: {config.bank_name}"
        if config.bank_account:
            line += f" — Account: {config.bank_account}"
        rows.append([Paragraph(line, STYLE_TERMS)])
    if config.mobile_money:
        rows.append([Paragraph(f"Mobile Money: {config.mobile_money}", STYLE_TERMS)])

    rows.append([Paragraph(
        config.invoice_footer or "Payment is due within 30 days. Thank you for your business.",
        STYLE_TERMS
    )])

    tbl = Table(rows, colWidths=[16 * cm])
    tbl.setStyle(TableStyle([
        ('LINEABOVE',    (0, 0), (-1, 0), 0.5, LIGHT_GREY),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING',   (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
        ('TOPPADDING',   (0, 0), (-1, 0), 10),
    ]))
    return tbl


def _totals_area(currency_symbol, subtotal, tax_amount, total_amount,
                 include_vat, vat_percent,
                 amount_paid=None, balance_due=None,
                 thank_text='Thank you for your business!'):
    left = Paragraph(thank_text, STYLE_THANK)
    right = _totals_table(
        currency_symbol, subtotal, tax_amount, total_amount,
        include_vat, vat_percent,
        amount_paid=amount_paid, balance_due=balance_due,
    )
    tbl = Table([[left, right]], colWidths=[8.4 * cm, 7.6 * cm])
    tbl.setStyle(TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'BOTTOM'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
    ]))
    return tbl


# ---------------------------------------------------------------------------
# Public render functions
# ---------------------------------------------------------------------------
def render_invoice_pdf(invoice, config, logo_data_uri=None):
    buffer = io.BytesIO()
    doc = _VerticalLabelDoc(
        buffer,
        doc_type='INVOICE',
        doc_number=invoice.invoice_number,
        title=f"Invoice {invoice.invoice_number}",
        author=config.company_name,
        subject=f"Invoice for {invoice.client.name}",
        creator=config.company_name,
    )

    vat_percent = f"{float(config.vat_rate) * 100:.1f}"
    story = [
        _header_table(config, logo_data_uri),
        Spacer(1, 14),
        _parties_table(
            config, invoice.client,
            'Invoice Date', invoice.issue_date.strftime('%d/%m/%Y'),
            'Due Date',     invoice.due_date.strftime('%d/%m/%Y'),
            bill_to_label='Bill To',
        ),
        Spacer(1, 14),
        _items_table(invoice.items.all(), config.currency_symbol),
        Spacer(1, 16),
        _totals_area(
            config.currency_symbol,
            invoice.subtotal, invoice.tax_amount, invoice.total_amount,
            include_vat=invoice.include_vat,
            vat_percent=vat_percent,
            amount_paid=invoice.amount_paid,
            balance_due=invoice.balance_due,
        ),
        Spacer(1, 22),
        _terms_table(config, invoice.notes),
    ]

    doc.build(story)
    return buffer.getvalue()


def render_quotation_pdf(quotation, config, logo_data_uri=None):
    buffer = io.BytesIO()
    doc = _VerticalLabelDoc(
        buffer,
        doc_type='QUOTATION',
        doc_number=quotation.quotation_number,
        title=f"Quotation {quotation.quotation_number}",
        author=config.company_name,
        subject=f"Quotation for {quotation.client.name}",
        creator=config.company_name,
    )

    vat_percent = f"{float(config.vat_rate) * 100:.1f}"
    story = [
        _header_table(config, logo_data_uri),
        Spacer(1, 14),
        _parties_table(
            config, quotation.client,
            'Issue Date',  quotation.issue_date.strftime('%d/%m/%Y'),
            'Valid Until', quotation.valid_until.strftime('%d/%m/%Y'),
            bill_to_label='Prepared For',
        ),
        Spacer(1, 14),
        _items_table(quotation.items.all(), config.currency_symbol),
        Spacer(1, 16),
        _totals_area(
            config.currency_symbol,
            quotation.subtotal, quotation.tax_amount, quotation.total_amount,
            include_vat=quotation.include_vat,
            vat_percent=vat_percent,
            thank_text='Thank you for considering our proposal!',
        ),
        Spacer(1, 16),
    ]

    # Validity notice
    validity = Table(
        [[Paragraph(
            f'This quotation is valid until '
            f'<b>{quotation.valid_until.strftime("%d/%m/%Y")}</b>. '
            f'Prices and availability are subject to change after this date.',
            STYLE_VALIDITY
        )]],
        colWidths=[16 * cm],
    )
    validity.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), AMBER_BG),
        ('BOX',          (0, 0), (-1, -1), 0.5, AMBER_BORDER),
        ('LEFTPADDING',  (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING',   (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 7),
    ]))
    story.append(validity)
    story.append(Spacer(1, 14))
    story.append(_terms_table(config, quotation.notes))

    doc.build(story)
    return buffer.getvalue()