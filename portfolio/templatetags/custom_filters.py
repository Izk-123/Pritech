from django import template

register = template.Library()

@register.filter
def split(value, delimiter):
    """Split a string by the given delimiter and return a list."""
    if not isinstance(value, str):
        return []
    return value.split(delimiter)

@register.filter
def replace(value, arg):
    """Usage: {{ value|replace:"_:" }}  (splits on first colon)"""
    if not isinstance(value, str):
        return value
    parts = arg.split(':')
    if len(parts) != 2:
        return value
    return value.replace(parts[0], parts[1])