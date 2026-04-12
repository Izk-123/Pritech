from django import template

register = template.Library()


@register.filter
def dict_get(d, key):
    """{{ mydict|dict_get:key }}"""
    if isinstance(d, dict):
        return d.get(key, 0)
    return 0


@register.filter
def replace(value, args):
    """{{ value|replace:"_: " }}  — replaces first arg with second"""
    try:
        old, new = args.split(':')
        return str(value).replace(old, new)
    except (ValueError, AttributeError):
        return value


@register.filter
def currency(value, symbol='K'):
    """{{ amount|currency:'K' }}"""
    try:
        return f"{symbol} {float(value):,.2f}"
    except (ValueError, TypeError):
        return value


@register.simple_tag(takes_context=True)
def active_nav(context, url_name):
    """{% active_nav 'ticket_list' %} → 'active' if current URL matches"""
    request = context.get('request')
    if not request:
        return ''
    from django.urls import reverse, NoReverseMatch
    try:
        if request.path.startswith(reverse(url_name)):
            return 'active'
    except NoReverseMatch:
        pass
    return ''
