# infrastructure/pdf_sanitizer.py
import bleach

ALLOWED_TAGS = [
    'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'h1', 'h2', 'h3', 'h4',
    'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'span', 'div',
]
ALLOWED_ATTRIBUTES = {
    '*': ['class', 'style'],
    'span': ['style'],
    'div': ['style'],
}

def sanitize_html(html_content):
    """Remove dangerous tags and attributes from HTML."""
    if not html_content:
        return ''
    return bleach.clean(html_content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)

def sanitize_plain_text(text):
    """Escape plain text for safe insertion into HTML."""
    if not text:
        return ''
    return bleach.clean(text, tags=[], strip=True)