# accounts/templatetags/account_tags.py
from django import template

register = template.Library()


@register.filter(name='has_perm')
def has_perm(user, perm_code):
    """Check if user has specific permission code."""
    if user.is_authenticated:
        return user.has_perm_code(perm_code)
    return False


@register.filter(name='has_role')
def has_role(user, role_code):
    """Check if user has specific role."""
    if user.is_authenticated:
        return user.has_role(role_code)
    return False