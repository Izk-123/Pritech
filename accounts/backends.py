# accounts/backends.py
"""
Custom authentication backends for the Pritech Accounts app.

* EmailOrPhoneBackend
    Allows logging in with either email OR phone number + password.

    Additionally hardened against accounts that were created through
    allauth's own signup endpoint *before* it was disabled – those have an
    EmailAddress row but stay unverified, and would otherwise be able to
    log in as soon as is_active is toggled to True.

  Verification rule:
    - User has no allauth EmailAddress rows at all
        → came through /accounts/register/ (or phone-only)
        → trust is_active (they became active after clicking the link)
    - User has allauth EmailAddress rows
        → came through social login or legacy allauth signup
        → require at least one verified address, otherwise deny.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

User = get_user_model()


class EmailOrPhoneBackend(ModelBackend):
    """Allow login with email OR phone number + password."""

    # ------------------------------------------------------------------
    # authenticate
    # ------------------------------------------------------------------
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        user = self._lookup_user(username)
        if user is None:
            return None

        if not user.check_password(password):
            return None

        if not self.user_can_authenticate(user):
            return None

        # Allauth-layer verification check (see module docstring).
        if not self._email_verified_for_allauth_user(user):
            return None

        return user

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _lookup_user(username: str):
        """
        Find a user by exact email (case-insensitive) OR phone number.
        Handles the edge case where two users share an email/phone pair
        due to historic data – returns the oldest record.
        """
        lookup = Q(email__iexact=username) | Q(phone_number=username)
        try:
            return User.objects.get(lookup)
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            return User.objects.filter(lookup).order_by("date_joined", "id").first()

    @staticmethod
    def _email_verified_for_allauth_user(user) -> bool:
        """
        Return True if the user is allowed to log in from an
        allauth-verification standpoint.

        * Users with no EmailAddress rows → trusted (custom flow).
        * Users WITH EmailAddress rows    → at least one must be verified.
        """
        if not user.email:
            return True  # phone-only user – nothing to verify

        try:
            from allauth.account.models import EmailAddress
        except ImportError:  # pragma: no cover – allauth always installed here
            return True

        addresses = EmailAddress.objects.filter(user=user)
        if not addresses.exists():
            # Custom registration flow – verification enforced by is_active.
            return True

        return addresses.filter(verified=True).exists()