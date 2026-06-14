# core/templatetags/sanitize_quill.py
import bleach
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ALLOWED_TAGS = [
    'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'strike', 's',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'code', 'pre',
    'ul', 'ol', 'li', 'a', 'img', 'span', 'div', 'table', 'thead', 'tbody',
    'tr', 'th', 'td', 'hr',
]
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target'],
    'img': ['src', 'alt', 'width', 'height'],
    'span': ['style', 'class'],
    'div': ['class'],
    '*': ['class'],
}

@register.filter
def sanitize_quill(value):
    if value is None:
        return ''
    if hasattr(value, 'html'):
        raw = value.html
    else:
        raw = str(value)
    cleaned = bleach.clean(raw, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
    return mark_safe(cleaned)