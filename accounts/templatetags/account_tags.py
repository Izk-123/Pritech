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


@register.filter(name='has_any_role')
def has_any_role(user, roles_string):
    """
    Check if user has any of the given roles.
    Usage: {{ user|has_any_role:'SUPER_ADMIN,ADMIN' }}
    """
    if not user or not user.is_authenticated:
        return False
    roles = [role.strip() for role in roles_string.split(',')]
    return any(user.has_role(role) for role in roles)