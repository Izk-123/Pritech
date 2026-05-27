# core/templatetags/custom_filters.py
from django import template

register = template.Library()


@register.filter
def replace(value, arg):
    """
    Replaces all occurrences of the first argument with the second argument.
    Usage: {{ value|replace:"old:new" }}
    """
    if ':' not in arg:
        return value  # or raise error
    old, new = arg.split(':', 1)
    return value.replace(old, new)