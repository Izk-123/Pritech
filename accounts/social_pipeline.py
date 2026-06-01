# accounts/social_pipeline.py
from django.contrib.auth import get_user_model
from allauth.socialaccount.models import SocialAccount
from clients.models import ClientOrganization
from accounts.models import Role, UserRole
import random

User = get_user_model()

def create_client_user(strategy, details, response, user=None, *args, **kwargs):
    """
    If the user does not exist, create a new user with type='client'.
    Also create a dummy client organization (can be updated later).
    """
    if user:
        # User already exists – maybe link social account (handled by allauth)
        return

    email = details.get('email')
    first_name = details.get('first_name', '')
    last_name = details.get('last_name', '')
    if not email:
        return

    # Create inactive user (will be activated after email verification? but social email is verified)
    new_user = User.objects.create_user(
        username=email,
        email=email,
        first_name=first_name,
        last_name=last_name,
        user_type='client',
        is_active=True,          # social accounts are considered verified
        client_role='viewer',    # default role, admin can promote later
    )
    new_user.set_unusable_password()   # no password needed
    new_user.save()

    # Create a default client organization
    org_name = f"{details.get('company_name') or first_name}'s Company"
    client_org = ClientOrganization.objects.create(
        name=org_name,
        email=email,
        user=new_user,
        status='active',
    )
    new_user.client_organization = client_org
    new_user.save()

    # Assign CLIENT role
    role, _ = Role.objects.get_or_create(code='CLIENT', defaults={'name': 'Client'})
    UserRole.objects.create(user=new_user, role=role)

    return {'user': new_user}