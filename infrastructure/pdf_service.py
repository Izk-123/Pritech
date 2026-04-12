import io
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.conf import settings


def render_pdf(template_name: str, context: dict) -> bytes:
    """Render a Django template to PDF bytes using WeasyPrint."""
    from weasyprint import HTML, CSS
    html_string = render_to_string(template_name, context)
    pdf_bytes = HTML(string=html_string, base_url=settings.BASE_DIR).write_pdf()
    return pdf_bytes


def pdf_response(pdf_bytes: bytes, filename: str) -> HttpResponse:
    """Return an HttpResponse that forces PDF download."""
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def pdf_inline_response(pdf_bytes: bytes, filename: str) -> HttpResponse:
    """Return an HttpResponse that opens PDF in browser."""
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response
