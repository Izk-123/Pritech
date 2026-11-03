# accounts/adapters.py
"""
allauth adapters for the Pritech Accounts app.

Two adapters are defined:

  * CustomAccountAdapter
        Blocks allauth's *own* signup page at /social/accounts/signup/.
        Every client registration must go through /accounts/register/, which
        enforces email verification, org creation, and role assignment.

  * SocialAccountAdapter
        Handles Google / LinkedIn signup: auto-creates a client user,
        a default organisation, and the CLIENT role.

Note: SocialAccountAdapter does NOT inherit from CustomAccountAdapter,
so blocking regular signup has no effect on social sign-in.
"""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.http import HttpRequest
from django.shortcuts import render

from clients.models import ClientOrganization
from accounts.models import Role, UserRole

User = get_user_model()


# ============================================================================
# Regular (email/password) signup adapter
# ============================================================================

class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Disable allauth's built-in signup page.

    Rationale:
        * /accounts/register/  – our own view – creates users with
          is_active=False and requires an emailed verification token.
        * /social/accounts/signup/ – allauth's view – creates users with
          is_active=True and (when ACCOUNT_EMAIL_VERIFICATION is not
          'mandatory') lets them log in immediately. That was the loophole
          letting fake-email accounts onto the platform.

    Setting is_open_for_signup() to False closes it. Users hitting the
    URL now see allauth's "signup closed" page instead of getting an
    active account.

    Social sign-in is unaffected because SocialAccountAdapter overrides
    its own is_open_for_signup() with a different signature.
    """

    def is_open_for_signup(self, request: HttpRequest) -> bool:  # noqa: D401
        return False


# ============================================================================
# Social sign-in adapter (Google / LinkedIn)
# ============================================================================

class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Customisations for allauth social login:

      * ``get_site`` strips the port from the host so ``Site.objects.get``
        works on local dev (127.0.0.1:8000).

      * ``populate_user`` forces user_type='client' and client_role='viewer'
        for brand-new social users.

      * ``save_user`` auto-creates a default ClientOrganization and assigns
        the CLIENT role, mirroring the /accounts/register/ flow.

      * ``render_authentication_error`` / ``render_cancel`` route to
        project-specific templates instead of allauth's defaults.
    """

    # ------------------------------------------------------------------
    # Site resolution (needed for dev)
    # ------------------------------------------------------------------
    def get_site(self, request: HttpRequest) -> Site:
        """
        allauth normally looks up Site.objects.get_current(), which needs
        request.get_host() exactly. During dev that includes ``:8000``,
        breaking Site lookups. Strip the port first.
        """
        host = request.get_host()
        if ":" in host:
            host = host.split(":", 1)[0]
        return Site.objects.get(domain=host)

    # ------------------------------------------------------------------
    # User population
    # ------------------------------------------------------------------
    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        user.user_type = "client"
        user.client_role = "viewer"
        user.is_active = True  # provider-verified emails (Google / LinkedIn)
        return user

    # ------------------------------------------------------------------
    # Post-save: create org + role
    # ------------------------------------------------------------------
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)

        org_name = (
            f"{user.first_name}'s Company"
            if user.first_name
            else f"{user.email.split('@')[0]}'s Company"
        )
        client_org, created = ClientOrganization.objects.get_or_create(
            email=user.email,
            defaults={
                "name": org_name,
                "user": user,
                "status": "active",
            },
        )
        if created:
            user.client_organization = client_org
            user.save(update_fields=["client_organization"])

        role, _ = Role.objects.get_or_create(
            code="CLIENT", defaults={"name": "Client"}
        )
        UserRole.objects.get_or_create(user=user, role=role)

        return user

    # ------------------------------------------------------------------
    # User-facing error / cancel pages
    # ------------------------------------------------------------------
    def render_authentication_error(
        self,
        request,
        provider_id,
        error=None,
        exception=None,
        extra_context=None,
    ):
        context = {"auth_error": error, "provider_id": provider_id}
        if extra_context:
            context.update(extra_context)
        return render(
            request,
            "socialaccount/authentication_error.html",
            context,
            status=400,
        )

    def render_cancel(self, request):
        return render(request, "socialaccount/login_cancelled.html", {}, status=200)