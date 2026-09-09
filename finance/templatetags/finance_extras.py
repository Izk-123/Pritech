# finance/templatetags/finance_extras.py
from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiply a value by an argument (e.g., 0.175 * 100 = 17.5)."""
    try:
        return value * arg
    except (TypeError, ValueError):
        return value