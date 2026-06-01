# accounts/adapters.py
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.sites.models import Site
from django.http import HttpRequest
from django.contrib.auth import get_user_model
from clients.models import ClientOrganization
from accounts.models import Role, UserRole

User = get_user_model()

class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def get_site(self, request: HttpRequest):
        """
        Override to strip the port from the host before getting the current site.
        """
        host = request.get_host()          # e.g., "127.0.0.1:8000"
        # Remove port if present
        if ':' in host:
            host = host.split(':')[0]      # becomes "127.0.0.1"
        return Site.objects.get(domain=host)

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        user.user_type = 'client'
        user.client_role = 'viewer'
        user.is_active = True
        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        # Create a default client organization
        org_name = f"{user.first_name}'s Company" if user.first_name else f"{user.email.split('@')[0]}'s Company"
        client_org, created = ClientOrganization.objects.get_or_create(
            email=user.email,
            defaults={
                'name': org_name,
                'user': user,
                'status': 'active',
            }
        )
        if created:
            user.client_organization = client_org
            user.save()
        # Assign CLIENT role
        role, _ = Role.objects.get_or_create(code='CLIENT', defaults={'name': 'Client'})
        UserRole.objects.get_or_create(user=user, role=role)
        return user