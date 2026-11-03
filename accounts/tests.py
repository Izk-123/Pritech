# accounts/tests.py
"""
Comprehensive test suite for the Pritech Accounts app.

Coverage map
------------
 1. Email deliverability validator      – MX + disposable layers
 2. Forms                               – every user-creating form
 3. Login backend                       – email/phone, inactive, allauth gate
 4. Registration view                   – inactive user, org+role, email sent
 5. Email verification view             – valid / expired / invalid / idempotent
 6. Resend verification                 – rotates token, no enumeration, rate-limit
 7. Login view                          – nudge on inactive, no state leak, rate-limit
 8. Adapters                            – allauth signup closed, social provisioning
 9. EmailVerificationToken model        – validity window + refresh
10. 2FA setup / disable / verify        – TOTP + recovery-code paths
11. Staff user management               – create / update / delete / access
12. ClientProfileEditView               – profile + organisation persistence
13. Recovery codes                      – list + regenerate
14. End-to-end verification journey     – register → verify → login

Run
---
    python manage.py test accounts.tests -v 2
    python manage.py test accounts.tests --settings=pritech.test_settings -v 1
    coverage run --source=accounts manage.py test accounts.tests --settings=pritech.test_settings

Notes
-----
* DNS is always mocked – no network calls leave the test runner.
* Outbound email uses Django's ``locmem`` backend – captured via ``mail.outbox``.
* Every class that touches the rate-limiter clears the cache in ``setUp`` so
  tests are order-independent.
* Every class that touches user creation patches the MX lookup so no real DNS
  query is issued (fast and hermetic).

── FIXED IN THIS VERSION ────────────────────────────────────────────────────
``StaffUserManagementTests.test_cannot_delete_superuser``
    Old version called ``User.objects.create_superuser()`` and then asserted
    only that the user still existed after the delete. In this project,
    ``create_superuser`` returns an object whose ``is_superuser`` /
    ``is_staff`` flags sometimes fail to persist to the DB, so the view
    correctly saw a non-privileged user and deleted it — and the test
    failed with an opaque ``assertTrue(exists())`` trace.

    New version:
      * Creates the account via ``create_user(..., is_superuser=True,
        is_staff=True)`` — explicit flags, no dependence on
        ``create_superuser``'s ``setdefault`` internals.
      * Asserts the flags really landed in the DB *before* the delete.
      * On failure, prints the actual DB row so you can tell instantly
        whether the MODEL or the VIEW is at fault.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from accounts.backends import EmailOrPhoneBackend
from accounts.forms import (
    ClientRegisterForm,
    InviteTeamMemberForm,
    StaffUserCreationForm,
)
from accounts.models import (
    EmailVerificationToken,
    RecoveryCode,
    Role,
    UserRole,
)
from accounts.validators import validate_email_deliverable
from clients.models import ClientOrganization

User = get_user_model()


# ============================================================================
# Test helpers
# ============================================================================

def create_user(email="test@example.com", *, active=True, user_type="client",
                password="testpass123!", **kwargs):
    """Create a User directly (bypasses the form and its validators)."""
    return User.objects.create_user(
        username=email,
        email=email,
        password=password,
        user_type=user_type,
        is_active=active,
        **kwargs,
    )


def clear_dns_cache():
    """Reset the ``lru_cache`` on the MX resolver between tests."""
    from accounts.validators import _domain_can_receive_mail
    _domain_can_receive_mail.cache_clear()


def _patch_mx(return_value=True):
    """Patch the MX check so tests never hit real DNS."""
    patcher = patch(
        "accounts.validators._domain_can_receive_mail",
        return_value=return_value,
    )
    patcher.start()
    clear_dns_cache()
    return patcher


# ============================================================================
# 1. Email deliverability validator
# ============================================================================

class EmailDeliverableValidatorTests(TestCase):
    """Validates the two-layer check (disposable + MX) at the field level."""

    def setUp(self):
        self.mx = _patch_mx(True)
        self.addCleanup(self.mx.stop)

    # --- valid addresses ---------------------------------------------------
    def test_normal_email_passes(self):
        validate_email_deliverable("alice@example.com")

    def test_gmail_passes(self):
        validate_email_deliverable("alice@gmail.com")

    def test_email_case_insensitive(self):
        validate_email_deliverable("Alice@EXAMPLE.com")

    def test_whitespace_trimmed(self):
        validate_email_deliverable("  alice@example.com  ")

    # --- disposable domains ------------------------------------------------
    def test_mailinator_blocked(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_email_deliverable("x@mailinator.com")
        self.assertIn("disposable", str(ctx.exception).lower())

    def test_10minutemail_blocked(self):
        with self.assertRaises(ValidationError):
            validate_email_deliverable("x@10minutemail.com")

    def test_yopmail_blocked(self):
        with self.assertRaises(ValidationError):
            validate_email_deliverable("x@yopmail.com")

    # --- MX failures -------------------------------------------------------
    def test_no_mx_blocked(self):
        with patch(
            "accounts.validators._domain_can_receive_mail",
            return_value=False,
        ):
            with self.assertRaises(ValidationError) as ctx:
                validate_email_deliverable("x@does-not-exist-xyz.com")
            self.assertIn("cannot receive", str(ctx.exception).lower())

    # --- malformed input ---------------------------------------------------
    def test_no_at_sign(self):
        with self.assertRaises(ValidationError):
            validate_email_deliverable("not-an-email")

    def test_empty_string(self):
        with self.assertRaises(ValidationError):
            validate_email_deliverable("")

    def test_none(self):
        with self.assertRaises(ValidationError):
            validate_email_deliverable(None)


class MxLookupTests(TestCase):
    """Exercises the actual DNS layer with mocked resolvers."""

    def setUp(self):
        clear_dns_cache()

    def tearDown(self):
        clear_dns_cache()

    def test_mx_present(self):
        from accounts import validators
        with patch("accounts.validators.dns.resolver.resolve") as mock_resolve:
            mock_resolve.return_value = ["mx1.example.com"]
            self.assertTrue(validators._domain_can_receive_mail("example.com"))

    def test_nxdomain_returns_false(self):
        import dns.resolver
        from accounts import validators
        with patch(
            "accounts.validators.dns.resolver.resolve",
            side_effect=dns.resolver.NXDOMAIN,
        ):
            self.assertFalse(validators._domain_can_receive_mail("nope.invalid"))

    def test_no_mx_falls_back_to_a_record(self):
        import dns.resolver
        from accounts import validators

        def fake_resolve(domain, record_type, lifetime):
            if record_type == "MX":
                raise dns.resolver.NoAnswer
            return ["1.2.3.4"]

        with patch(
            "accounts.validators.dns.resolver.resolve",
            side_effect=fake_resolve,
        ):
            self.assertTrue(validators._domain_can_receive_mail("fallback.com"))

    def test_timeout_fails_open(self):
        import dns.exception
        from accounts import validators
        with patch(
            "accounts.validators.dns.resolver.resolve",
            side_effect=dns.exception.Timeout,
        ):
            # Fail-open: our resolver being down must NOT block users
            self.assertTrue(validators._domain_can_receive_mail("slow.com"))

    def test_lru_cache_avoids_repeat_lookups(self):
        from accounts import validators
        with patch(
            "accounts.validators.dns.resolver.resolve",
            return_value=["mx"],
        ) as mock_resolve:
            validators._domain_can_receive_mail("cacheme.com")
            validators._domain_can_receive_mail("cacheme.com")
            self.assertEqual(mock_resolve.call_count, 1)


# ============================================================================
# 2. Forms
# ============================================================================

class ClientRegisterFormTests(TestCase):
    def setUp(self):
        self.mx = _patch_mx(True)
        self.addCleanup(self.mx.stop)

    def _data(self, **overrides):
        data = {
            "first_name": "Alice",
            "last_name": "Doe",
            "email": "alice@example.com",
            "phone_number": "+265991234567",
            "physical_address": "Lilongwe",
            "password": "Str0ng!Pass",
            "confirm_password": "Str0ng!Pass",
            "company_name": "Acme Ltd",
        }
        data.update(overrides)
        return data

    def test_valid_form(self):
        form = ClientRegisterForm(data=self._data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_password_mismatch(self):
        form = ClientRegisterForm(
            data=self._data(confirm_password="Different!")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("do not match", str(form.errors).lower())

    def test_disposable_email_rejected(self):
        form = ClientRegisterForm(
            data=self._data(email="x@mailinator.com")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("disposable", str(form.errors).lower())

    def test_no_mx_rejected(self):
        with patch(
            "accounts.validators._domain_can_receive_mail",
            return_value=False,
        ):
            form = ClientRegisterForm(
                data=self._data(email="x@fake-xyz-999.com")
            )
            self.assertFalse(form.is_valid())
            self.assertIn("cannot receive", str(form.errors).lower())

    def test_email_lowercased(self):
        form = ClientRegisterForm(
            data=self._data(email="ALICE@EXAMPLE.COM")
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["email"], "alice@example.com")

    def test_duplicate_email_rejected(self):
        create_user("alice@example.com")
        form = ClientRegisterForm(data=self._data())
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", str(form.errors).lower())

    def test_duplicate_email_case_insensitive(self):
        create_user("alice@example.com")
        form = ClientRegisterForm(
            data=self._data(email="ALICE@EXAMPLE.COM")
        )
        self.assertFalse(form.is_valid())


class InviteTeamMemberFormTests(TestCase):
    def setUp(self):
        self.mx = _patch_mx(True)
        self.addCleanup(self.mx.stop)

    def test_disposable_rejected(self):
        form = InviteTeamMemberForm(data={
            "email": "x@mailinator.com",
            "first_name": "A", "last_name": "B",
            "role": "viewer",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("disposable", str(form.errors).lower())

    def test_existing_user_rejected(self):
        create_user("existing@example.com")
        form = InviteTeamMemberForm(data={
            "email": "existing@example.com",
            "first_name": "A", "last_name": "B",
            "role": "viewer",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", str(form.errors).lower())


class StaffUserCreationFormTests(TestCase):
    def setUp(self):
        self.mx = _patch_mx(True)
        self.addCleanup(self.mx.stop)

    def test_disposable_rejected(self):
        form = StaffUserCreationForm(data={
            "email": "staff@mailinator.com",
            "first_name": "A", "last_name": "B",
            "phone_number": "+265991234567",
            "user_type": "staff",
            "password1": "Str0ng!Pass",
            "password2": "Str0ng!Pass",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("disposable", str(form.errors).lower())


# ============================================================================
# 3. Login backend
# ============================================================================

class EmailOrPhoneBackendTests(TestCase):
    def setUp(self):
        self.backend = EmailOrPhoneBackend()

    def test_email_login(self):
        user = create_user("alice@example.com", password="secret123")
        self.assertEqual(
            self.backend.authenticate(
                None, username="alice@example.com", password="secret123"
            ),
            user,
        )

    def test_email_case_insensitive(self):
        user = create_user("alice@example.com", password="secret123")
        self.assertEqual(
            self.backend.authenticate(
                None, username="ALICE@EXAMPLE.COM", password="secret123"
            ),
            user,
        )

    def test_phone_login(self):
        user = create_user(
            "alice@example.com",
            password="secret123",
            phone_number="+265991234567",
        )
        self.assertEqual(
            self.backend.authenticate(
                None, username="+265991234567", password="secret123"
            ),
            user,
        )

    def test_wrong_password_returns_none(self):
        create_user("alice@example.com", password="secret123")
        self.assertIsNone(
            self.backend.authenticate(
                None, username="alice@example.com", password="wrong"
            )
        )

    def test_unknown_user_returns_none(self):
        self.assertIsNone(
            self.backend.authenticate(
                None, username="nobody@example.com", password="whatever"
            )
        )

    def test_inactive_user_blocked(self):
        create_user("alice@example.com", password="secret123", active=False)
        self.assertIsNone(
            self.backend.authenticate(
                None, username="alice@example.com", password="secret123"
            )
        )

    def test_missing_credentials(self):
        self.assertIsNone(
            self.backend.authenticate(None, username="", password="")
        )
        self.assertIsNone(
            self.backend.authenticate(None, username="a", password=None)
        )

    def test_allauth_unverified_blocked(self):
        """An allauth EmailAddress row that is unverified must block login."""
        try:
            from allauth.account.models import EmailAddress
        except ImportError:
            self.skipTest("allauth not installed")

        user = create_user("alice@example.com", password="secret123")
        EmailAddress.objects.create(
            user=user, email=user.email, verified=False, primary=True
        )
        self.assertIsNone(
            self.backend.authenticate(
                None, username="alice@example.com", password="secret123"
            )
        )

    def test_allauth_verified_passes(self):
        try:
            from allauth.account.models import EmailAddress
        except ImportError:
            self.skipTest("allauth not installed")

        user = create_user("alice@example.com", password="secret123")
        EmailAddress.objects.create(
            user=user, email=user.email, verified=True, primary=True
        )
        self.assertEqual(
            self.backend.authenticate(
                None, username="alice@example.com", password="secret123"
            ),
            user,
        )

    def test_custom_flow_user_without_emailaddress_passes(self):
        """Users from /accounts/register/ have no allauth row → trusted."""
        user = create_user("alice@example.com", password="secret123")
        self.assertEqual(
            self.backend.authenticate(
                None, username="alice@example.com", password="secret123"
            ),
            user,
        )


# ============================================================================
# 4. Registration view
# ============================================================================

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ClientRegisterViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.mx = _patch_mx(True)
        self.addCleanup(self.mx.stop)

    def _post(self, **overrides):
        data = {
            "first_name": "Alice",
            "last_name": "Doe",
            "email": "alice@example.com",
            "phone_number": "+265991234567",
            "physical_address": "Lilongwe",
            "password": "Str0ng!Pass",
            "confirm_password": "Str0ng!Pass",
            "company_name": "Acme Ltd",
        }
        data.update(overrides)
        return self.client.post(reverse("register"), data=data)

    def test_successful_registration_redirects_to_check_email(self):
        response = self._post()
        self.assertRedirects(response, reverse("check_your_email"))

    def test_user_created_inactive(self):
        self._post()
        user = User.objects.get(email="alice@example.com")
        self.assertFalse(user.is_active)
        self.assertEqual(user.user_type, "client")
        self.assertEqual(user.username, "alice@example.com")

    def test_organisation_created_and_linked(self):
        self._post()
        user = User.objects.get(email="alice@example.com")
        self.assertIsNotNone(user.client_organization)
        self.assertEqual(user.client_organization.name, "Acme Ltd")

    def test_client_role_assigned(self):
        self._post()
        user = User.objects.get(email="alice@example.com")
        self.assertTrue(
            UserRole.objects.filter(user=user, role__code="CLIENT").exists()
        )

    def test_verification_token_created(self):
        self._post()
        user = User.objects.get(email="alice@example.com")
        self.assertTrue(hasattr(user, "verification_token"))

    def test_verification_email_sent(self):
        self._post()
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn("alice@example.com", email.to)
        self.assertIn("Verify your email", email.subject)
        self.assertIn("/accounts/verify-email/", email.body)

    def test_session_flag_set(self):
        self._post()
        self.assertEqual(
            self.client.session.get("pending_verification_email"),
            "alice@example.com",
        )

    def test_smtp_failure_does_not_block_registration(self):
        """SMTP outage should not roll back the user creation."""
        with patch(
            "accounts.utils.send_mail",
            side_effect=Exception("SMTP down"),
        ):
            response = self._post()
        self.assertTrue(
            User.objects.filter(email="alice@example.com").exists()
        )
        self.assertRedirects(response, reverse("check_your_email"))

    def test_disposable_email_rejected(self):
        response = self._post(email="x@mailinator.com")
        self.assertEqual(response.status_code, 200)  # form re-rendered
        self.assertFalse(
            User.objects.filter(email="x@mailinator.com").exists()
        )


# ============================================================================
# 5. Verification view
# ============================================================================

class VerifyEmailViewTests(TestCase):
    def setUp(self):
        self.user = create_user("alice@example.com", active=False)
        self.token = EmailVerificationToken.objects.create(user=self.user)

    def _url(self, token=None):
        return reverse(
            "verify_email",
            kwargs={"token": (token or self.token.token)},
        )

    def test_valid_token_activates_user(self):
        response = self.client.get(self._url())
        self.assertRedirects(response, reverse("login"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_valid_token_is_deleted(self):
        self.client.get(self._url())
        self.assertFalse(
            EmailVerificationToken.objects.filter(user=self.user).exists()
        )

    def test_invalid_token_shows_error(self):
        import uuid
        response = self.client.get(self._url(token=uuid.uuid4()), follow=True)
        self.assertRedirects(response, reverse("login"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_expired_token_shows_expired_page(self):
        EmailVerificationToken.objects.filter(pk=self.token.pk).update(
            updated_at=timezone.now() - timedelta(hours=25)
        )
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "accounts/verification_expired.html"
        )
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_already_active_is_idempotent(self):
        self.user.is_active = True
        self.user.save()
        response = self.client.get(self._url())
        self.assertRedirects(response, reverse("login"))
        self.assertFalse(
            EmailVerificationToken.objects.filter(user=self.user).exists()
        )

    def test_clears_session_flag(self):
        session = self.client.session
        session["pending_verification_email"] = "alice@example.com"
        session.save()

        self.client.get(self._url())

        self.assertIsNone(
            self.client.session.get("pending_verification_email")
        )


# ============================================================================
# 6. Resend verification
# ============================================================================

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ResendVerificationViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = create_user("alice@example.com", active=False)

    def test_resend_sends_email(self):
        response = self.client.post(
            reverse("resend_verification"),
            {"email": "alice@example.com"},
        )
        self.assertRedirects(response, reverse("check_your_email"))
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_rotates_token(self):
        old = EmailVerificationToken.objects.create(user=self.user)
        old_value = str(old.token)

        self.client.post(
            reverse("resend_verification"),
            {"email": "alice@example.com"},
        )

        new = EmailVerificationToken.objects.get(user=self.user)
        self.assertNotEqual(str(new.token), old_value)

    def test_unknown_email_returns_same_success(self):
        """No user-enumeration: same message either way."""
        response = self.client.post(
            reverse("resend_verification"),
            {"email": "nobody@example.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_active_user_does_not_receive_email(self):
        create_user("active@example.com", active=True)
        self.client.post(
            reverse("resend_verification"),
            {"email": "active@example.com"},
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_rate_limit_blocks_after_three(self):
        for _ in range(3):
            self.client.post(
                reverse("resend_verification"),
                {"email": "alice@example.com"},
            )
        response = self.client.post(
            reverse("resend_verification"),
            {"email": "alice@example.com"},
        )
        self.assertEqual(response.status_code, 403)


# ============================================================================
# 7. Login view
# ============================================================================

class CustomLoginViewTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_active_user_login_succeeds(self):
        create_user("alice@example.com", active=True, password="secret123")
        response = self.client.post(
            reverse("login"),
            {"username": "alice@example.com", "password": "secret123"},
        )
        self.assertEqual(response.status_code, 302)

    def test_inactive_user_login_fails(self):
        create_user("alice@example.com", active=False, password="secret123")
        response = self.client.post(
            reverse("login"),
            {"username": "alice@example.com", "password": "secret123"},
        )
        self.assertEqual(response.status_code, 200)

    def test_inactive_user_gets_helpful_message(self):
        create_user("alice@example.com", active=False, password="secret123")
        response = self.client.post(
            reverse("login"),
            {"username": "alice@example.com", "password": "secret123"},
            follow=True,
        )
        msgs = [str(m) for m in response.context["messages"]]
        self.assertTrue(
            any("not yet activated" in m for m in msgs),
            f"Expected activation hint. Got: {msgs}",
        )

    def test_wrong_password_does_not_leak_state(self):
        """Wrong password on an inactive account must NOT reveal the state."""
        create_user("alice@example.com", active=False, password="secret123")
        response = self.client.post(
            reverse("login"),
            {"username": "alice@example.com", "password": "wrong"},
            follow=True,
        )
        msgs = [str(m) for m in response.context["messages"]]
        self.assertFalse(
            any("not yet activated" in m for m in msgs),
            "Should not reveal inactive state for wrong password",
        )

    def test_session_flag_set_on_inactive_login(self):
        create_user("alice@example.com", active=False, password="secret123")
        self.client.post(
            reverse("login"),
            {"username": "alice@example.com", "password": "secret123"},
        )
        self.assertEqual(
            self.client.session.get("pending_verification_email"),
            "alice@example.com",
        )

    def test_login_rate_limited(self):
        create_user("alice@example.com", active=True, password="secret123")
        for _ in range(10):
            self.client.post(
                reverse("login"),
                {"username": "alice@example.com", "password": "wrong"},
            )
        response = self.client.post(
            reverse("login"),
            {"username": "alice@example.com", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 403)


# ============================================================================
# 8. Adapters
# ============================================================================

class AccountAdapterTests(TestCase):
    def test_regular_signup_blocked(self):
        from accounts.adapters import CustomAccountAdapter
        adapter = CustomAccountAdapter()
        self.assertFalse(adapter.is_open_for_signup(None))


class SocialAccountAdapterTests(TestCase):
    @patch(
        "allauth.socialaccount.adapter."
        "DefaultSocialAccountAdapter.populate_user"
    )
    def test_populate_user_sets_defaults(self, mock_populate):
        from accounts.adapters import SocialAccountAdapter

        mock_populate.return_value = User(email="new@example.com")
        adapter = SocialAccountAdapter()
        user = adapter.populate_user(None, MagicMock(), {})

        self.assertEqual(user.user_type, "client")
        self.assertEqual(user.client_role, "viewer")
        self.assertTrue(user.is_active)


class SocialAccountAdapterSaveUserTests(TestCase):
    @patch(
        "allauth.socialaccount.adapter.DefaultSocialAccountAdapter.save_user"
    )
    def test_creates_client_org_and_role(self, mock_save):
        from accounts.adapters import SocialAccountAdapter

        user = User.objects.create(
            username="social@example.com",
            email="social@example.com",
            first_name="Social",
            user_type="client",
            client_role="viewer",
        )
        mock_save.return_value = user

        adapter = SocialAccountAdapter()
        result = adapter.save_user(None, MagicMock(), form=None)

        self.assertEqual(result, user)

        user.refresh_from_db()
        self.assertIsNotNone(user.client_organization)
        self.assertEqual(
            user.client_organization.email, "social@example.com"
        )
        self.assertEqual(user.client_organization.name, "Social's Company")
        self.assertTrue(
            UserRole.objects.filter(
                user=user, role__code="CLIENT"
            ).exists()
        )

    @patch(
        "allauth.socialaccount.adapter.DefaultSocialAccountAdapter.save_user"
    )
    def test_reuses_existing_org_for_same_email(self, mock_save):
        from accounts.adapters import SocialAccountAdapter

        ClientOrganization.objects.create(
            name="Existing Co",
            email="social@example.com",
            status="active",
        )
        user = User.objects.create(
            username="social@example.com",
            email="social@example.com",
            user_type="client",
        )
        mock_save.return_value = user

        SocialAccountAdapter().save_user(None, MagicMock())

        # Org count must not increase (get_or_create matched existing row)
        self.assertEqual(
            ClientOrganization.objects.filter(
                email="social@example.com"
            ).count(),
            1,
        )


# ============================================================================
# 9. EmailVerificationToken model
# ============================================================================

class EmailVerificationTokenModelTests(TestCase):
    def setUp(self):
        self.user = create_user("alice@example.com", active=False)

    def test_fresh_token_is_valid(self):
        token = EmailVerificationToken.objects.create(user=self.user)
        self.assertTrue(token.is_valid())

    def test_token_valid_just_under_24h(self):
        token = EmailVerificationToken.objects.create(user=self.user)
        EmailVerificationToken.objects.filter(pk=token.pk).update(
            updated_at=timezone.now() - timedelta(hours=23, minutes=59)
        )
        token.refresh_from_db()
        self.assertTrue(token.is_valid())

    def test_token_expires_after_24h(self):
        token = EmailVerificationToken.objects.create(user=self.user)
        EmailVerificationToken.objects.filter(pk=token.pk).update(
            updated_at=timezone.now() - timedelta(hours=24, seconds=1)
        )
        token.refresh_from_db()
        self.assertFalse(token.is_valid())

    def test_refresh_rotates_token(self):
        token = EmailVerificationToken.objects.create(user=self.user)
        old_value = str(token.token)
        token.refresh()
        token.refresh_from_db()
        self.assertNotEqual(str(token.token), old_value)

    def test_refresh_resets_clock(self):
        token = EmailVerificationToken.objects.create(user=self.user)
        EmailVerificationToken.objects.filter(pk=token.pk).update(
            updated_at=timezone.now() - timedelta(hours=20)
        )
        token.refresh_from_db()
        token.refresh()
        token.refresh_from_db()
        self.assertTrue(token.is_valid())
        self.assertLess(
            (timezone.now() - token.updated_at).total_seconds(),
            60,
        )


# ============================================================================
# 10. 2FA – setup / disable / verify
# ============================================================================

class TwoFactorSetupTests(TestCase):
    def setUp(self):
        self.user = create_user("alice@example.com")
        self.client.force_login(self.user)

    def test_setup_page_generates_qr_and_secret(self):
        resp = self.client.get(reverse("two_factor_setup"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("qr_code", resp.context)
        self.assertIn("secret_key", resp.context)
        # A new unconfirmed device should now exist
        self.assertTrue(
            TOTPDevice.objects.filter(
                user=self.user, confirmed=False
            ).exists()
        )

    def test_setup_enables_2fa_with_valid_totp(self):
        self.client.get(reverse("two_factor_setup"))
        device = TOTPDevice.objects.get(user=self.user, confirmed=False)
        token = str(totp(device.bin_key)).zfill(6)

        resp = self.client.post(
            reverse("two_factor_setup"), {"token": token}
        )
        self.assertRedirects(resp, reverse("profile"))

        device.refresh_from_db()
        self.assertTrue(device.confirmed)

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_2fa_enabled)

    def test_setup_rejects_wrong_token(self):
        self.client.get(reverse("two_factor_setup"))
        resp = self.client.post(
            reverse("two_factor_setup"), {"token": "000000"}
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_2fa_enabled)


class TwoFactorDisableTests(TestCase):
    def setUp(self):
        self.user = create_user("alice@example.com")
        TOTPDevice.objects.create(user=self.user, confirmed=True)
        self.user.is_2fa_enabled = True
        self.user.save()
        self.client.force_login(self.user)

    def test_post_removes_devices_and_flag(self):
        resp = self.client.post(reverse("two_factor_disable"))
        self.assertRedirects(resp, reverse("profile"))
        self.assertEqual(
            TOTPDevice.objects.filter(user=self.user).count(), 0
        )
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_2fa_enabled)

    def test_get_shows_confirmation(self):
        resp = self.client.get(reverse("two_factor_disable"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "accounts/two_factor_disable.html")


class TwoFactorVerifyTests(TestCase):
    def setUp(self):
        self.user = create_user("alice@example.com")
        self.user.is_2fa_enabled = True
        self.user.save()
        self.device = TOTPDevice.objects.create(
            user=self.user, confirmed=True
        )

    def _prime_session(self):
        session = self.client.session
        session["pre_2fa_user_id"] = str(self.user.pk)
        session.save()

    def test_get_without_session_redirects(self):
        resp = self.client.get(reverse("two_factor_verify"))
        self.assertRedirects(resp, reverse("login"))

    def test_verify_with_valid_totp_logs_in(self):
        self._prime_session()
        token = str(totp(self.device.bin_key)).zfill(6)
        resp = self.client.post(
            reverse("two_factor_verify"), {"token": token}
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "/dashboard/")

    def test_verify_with_recovery_code_marks_used(self):
        rc = RecoveryCode.objects.create(user=self.user, code="ABC123")
        self._prime_session()
        resp = self.client.post(
            reverse("two_factor_verify"), {"token": "ABC123"}
        )
        self.assertEqual(resp.status_code, 302)
        rc.refresh_from_db()
        self.assertTrue(rc.is_used)

    def test_verify_with_invalid_code_shows_error(self):
        self._prime_session()
        resp = self.client.post(
            reverse("two_factor_verify"), {"token": "000000"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "accounts/two_factor_verify.html")


# ============================================================================
# 11. Staff user management
# ============================================================================

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class StaffUserManagementTests(TestCase):
    def setUp(self):
        cache.clear()
        self.mx = _patch_mx(True)
        self.addCleanup(self.mx.stop)
        self.admin = User.objects.create_superuser(
            username="admin@example.com",
            email="admin@example.com",
            password="secret123",
            user_type="staff",
        )
        self.client.force_login(self.admin)

    # --- create --------------------------------------------------------
    def test_create_staff_user(self):
        resp = self.client.post(reverse("user_create"), {
            "email": "newstaff@example.com",
            "first_name": "New", "last_name": "Staff",
            "phone_number": "+265991111111",
            "user_type": "staff",
            "password1": "Str0ng!Pass",
            "password2": "Str0ng!Pass",
        })
        self.assertRedirects(resp, reverse("user_list"))
        new = User.objects.get(email="newstaff@example.com")
        self.assertEqual(new.user_type, "staff")
        self.assertTrue(new.check_password("Str0ng!Pass"))

    def test_create_assigns_roles(self):
        role = Role.objects.create(code="TECH", name="Technician")
        self.client.post(reverse("user_create"), {
            "email": "tech@example.com",
            "first_name": "T", "last_name": "U",
            "phone_number": "+265991111112",
            "user_type": "staff",
            "password1": "Str0ng!Pass",
            "password2": "Str0ng!Pass",
            "roles": [role.pk],
        })
        new = User.objects.get(email="tech@example.com")
        self.assertTrue(
            UserRole.objects.filter(user=new, role=role).exists()
        )

    # --- update --------------------------------------------------------
    def test_update_changes_role_membership(self):
        role_a = Role.objects.create(code="A", name="A")
        role_b = Role.objects.create(code="B", name="B")
        target = create_user("target@example.com", user_type="staff")
        UserRole.objects.create(user=target, role=role_a)

        self.client.post(reverse("user_update", args=[target.pk]), {
            "email": target.email,
            "first_name": "T", "last_name": "U",
            "phone_number": "",
            "user_type": "staff",
            "roles": [role_b.pk],  # swap A → B
        })

        self.assertFalse(
            UserRole.objects.filter(user=target, role=role_a).exists()
        )
        self.assertTrue(
            UserRole.objects.filter(user=target, role=role_b).exists()
        )

    # --- delete --------------------------------------------------------
    def test_delete_removes_user(self):
        target = create_user("gone@example.com", user_type="staff")
        resp = self.client.post(reverse("user_delete", args=[target.pk]))
        self.assertRedirects(resp, reverse("user_list"))
        self.assertFalse(User.objects.filter(pk=target.pk).exists())

    # ── FIXED ────────────────────────────────────────────────────────────
    # The old version called ``create_superuser()`` and got a user whose
    # ``is_superuser`` / ``is_staff`` flags did not persist to the DB.
    # The view correctly saw a non-privileged user, allowed the delete,
    # and the test failed with an opaque ``assertTrue(exists())`` trace.
    #
    # The new version:
    #   1. Creates the account with ``create_user(..., is_superuser=True,
    #      is_staff=True)`` — explicit flags, no dependence on
    #      ``create_superuser``'s ``setdefault`` internals.
    #   2. Refreshes from DB and asserts the flags really landed.
    #   3. Fails with a self-diagnosing message that shows the actual
    #      DB row if the sanity check ever fails.
    #   4. Only then exercises the delete endpoint.
    # ─────────────────────────────────────────────────────────────────────
    def test_cannot_delete_superuser(self):
        """
        A superuser must not be deletable via ``UserDeleteView``.

        If this test ever fails on the SETUP assertion, the model /
        manager is at fault (flags not persisting). If it fails on the
        GUARD assertion, the view's privilege check is at fault.
        """
        other_super = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="secret123",
            user_type="staff",
            is_superuser=True,
            is_staff=True,
        )

        # ── Sanity: flags must persist. If they don't, the model is broken.
        other_super.refresh_from_db()
        self.assertTrue(
            other_super.is_superuser,
            "SETUP FAILURE — is_superuser did not persist to the DB. "
            "This is a MODEL issue, not a view or test issue. "
            f"DB row: {User.objects.filter(pk=other_super.pk).values('is_superuser', 'is_staff', 'user_type').first()}",
        )
        self.assertTrue(
            other_super.is_staff,
            "SETUP FAILURE — is_staff did not persist to the DB. "
            f"DB row: {User.objects.filter(pk=other_super.pk).values('is_superuser', 'is_staff', 'user_type').first()}",
        )

        # ── Exercise the view
        resp = self.client.post(reverse("user_delete", args=[other_super.pk]))

        # ── Both branches (blocked + allowed) redirect to user_list.
        self.assertRedirects(resp, reverse("user_list"))

        # ── Final guard check
        self.assertTrue(
            User.objects.filter(pk=other_super.pk).exists(),
            "GUARD FAILURE — superuser was deleted despite the view's "
            "privilege check. Inspect UserDeleteView.delete().",
        )

    # --- access control ------------------------------------------------
    def test_non_staff_cannot_reach_user_list(self):
        client_user = create_user("c@example.com", user_type="client")
        self.client.force_login(client_user)
        resp = self.client.get(reverse("user_list"))
        self.assertEqual(resp.status_code, 302)  # to admin login

    def test_anonymous_cannot_reach_user_list(self):
        self.client.logout()
        resp = self.client.get(reverse("user_list"))
        self.assertEqual(resp.status_code, 302)


# ============================================================================
# 12. ClientProfileEditView
# ============================================================================

class ClientProfileEditTests(TestCase):
    def setUp(self):
        cache.clear()
        self.mx = _patch_mx(True)
        self.addCleanup(self.mx.stop)

        self.user = create_user("alice@example.com")
        self.org = ClientOrganization.objects.create(
            name="Old Name",
            email="old@example.com",
            user=self.user,
            status="active",
        )
        self.user.client_organization = self.org
        self.user.save()
        self.client.force_login(self.user)

    def test_update_profile_and_org(self):
        resp = self.client.post(reverse("client_profile_edit"), {
            "first_name": "Updated",
            "last_name": "Name",
            "email": "alice@example.com",   # unchanged
            "phone_number": "+265991234567",
            "physical_address": "New Addr",
            "company_name": "New Org Name",
            "company_phone": "+265990000000",
            "company_address": "New Org Addr",
            "company_email": "new@example.com",
        })
        self.assertRedirects(resp, reverse("profile"))
        self.user.refresh_from_db()
        self.org.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")
        self.assertEqual(self.org.name, "New Org Name")
        self.assertEqual(self.org.email, "new@example.com")

    def test_email_conflict_blocked(self):
        create_user("other@example.com")
        resp = self.client.post(reverse("client_profile_edit"), {
            "first_name": "A", "last_name": "B",
            "email": "other@example.com",   # collision
            "phone_number": "",
            "physical_address": "",
            "company_name": "Acme",
            "company_phone": "",
            "company_address": "",
            "company_email": "",
        })
        self.assertEqual(resp.status_code, 200)  # form re-rendered


# ============================================================================
# 13. Recovery codes
# ============================================================================

class RecoveryCodesViewTests(TestCase):
    def setUp(self):
        self.user = create_user("alice@example.com")
        self.client.force_login(self.user)

    def test_get_lists_codes(self):
        RecoveryCode.generate_for_user(self.user, num_codes=3)
        resp = self.client.get(reverse("recovery_codes"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["codes"].count(), 3)

    def test_post_regenerates_codes(self):
        RecoveryCode.generate_for_user(self.user, num_codes=2)
        self.client.post(reverse("recovery_codes"))
        self.assertEqual(
            RecoveryCode.objects.filter(
                user=self.user, is_used=False
            ).count(),
            10,
        )


# ============================================================================
# 14. End-to-end verification journey
# ============================================================================

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EndToEndVerificationFlowTests(TestCase):
    """Register → miss email → nudge → click link → login."""

    def setUp(self):
        cache.clear()
        self.mx = _patch_mx(True)
        self.addCleanup(self.mx.stop)

    def test_full_journey(self):
        import re

        # 1. Register
        self.client.post(reverse("register"), {
            "first_name": "Eve",
            "last_name": "Test",
            "email": "eve@example.com",
            "phone_number": "+265991234567",
            "physical_address": "Lilongwe",
            "password": "Str0ng!Pass",
            "confirm_password": "Str0ng!Pass",
            "company_name": "Eve Ltd",
        })
        self.assertEqual(len(mail.outbox), 1)

        # 2. Login attempt must fail (account inactive)
        resp = self.client.post(reverse("login"), {
            "username": "eve@example.com",
            "password": "Str0ng!Pass",
        })
        self.assertEqual(resp.status_code, 200)

        # 3. Click the verification link from the email
        body = mail.outbox[0].body
        m = re.search(r"/accounts/verify-email/[0-9a-f-]+/", body)
        self.assertIsNotNone(m, "No verification URL in email body")
        self.client.get(m.group(0))

        # 4. Login now succeeds
        resp = self.client.post(reverse("login"), {
            "username": "eve@example.com",
            "password": "Str0ng!Pass",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "/dashboard/")

        # 5. User is active
        self.assertTrue(
            User.objects.get(email="eve@example.com").is_active
        )