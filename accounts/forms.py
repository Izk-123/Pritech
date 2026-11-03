# accounts/forms.py
"""
Forms for the Accounts app.

This module handles:
  - Client self-registration
  - Login (via Email OR Phone)
  - Client profile & team management
  - 2FA token verification
  - Staff user management (Admin panel)
  - Role & Permission management

Email Handling Rules applied consistently:
  * Emails are stripped and lower-cased before persistence.
  * Every form creating/changing an email runs `validate_email_deliverable`
    (MX records + disposable-domain blocklist).
  * Email uniqueness is checked case-insensitively.
"""

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
    UserChangeForm,
)
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Permission, User, Role
from .validators import validate_email_deliverable


# ============================================================================
# Helpers
# ============================================================================

def _normalise_email(raw: str) -> str:
    """Lower-case and strip an email string."""
    return (raw or "").strip().lower()


def _email_in_use(email: str, exclude_pk=None) -> bool:
    """Case-insensitive check that a User with this email already exists."""
    qs = User.objects.filter(email__iexact=email)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


def _unique_username(email: str, exclude_pk=None) -> str:
    """
    Build a unique `username` from the email address.

    The project logs in with email (USERNAME_FIELD = "email") but AbstractUser
    still has a UNIQUE `username` column. If the form never fills it, every new
    user gets username="" and the second insert raises
    "UNIQUE constraint failed: accounts_user.username".
    """
    base = email[:150]
    candidate = base
    counter = 1
    while User.objects.filter(username__iexact=candidate).exclude(pk=exclude_pk).exists():
        suffix = f"-{counter}"
        candidate = f"{base[:150 - len(suffix)]}{suffix}"
        counter += 1
    return candidate


# ============================================================================
# 1. Client Registration
# ============================================================================

class ClientRegisterForm(forms.ModelForm):
    """Client self-registration form with organisation name."""

    company_name = forms.CharField(
        max_length=200,
        required=True,
        label="Company / Organisation name",
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"placeholder": "Password", "class": "form-control"}
        )
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"placeholder": "Confirm password", "class": "form-control"}
        )
    )

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "physical_address",
            "password",
            "company_name",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"placeholder": "First name", "class": "form-control"}),
            "last_name": forms.TextInput(attrs={"placeholder": "Last name", "class": "form-control"}),
            "email": forms.EmailInput(attrs={"placeholder": "Email address", "class": "form-control"}),
            "phone_number": forms.TextInput(attrs={"placeholder": "+265 999 000 000", "class": "form-control"}),
            "physical_address": forms.Textarea(attrs={"placeholder": "Your address", "rows": 2, "class": "form-control"}),
        }

    def clean_email(self):
        email = _normalise_email(self.cleaned_data["email"])
        validate_email_deliverable(email)          # MX + disposable check
        if _email_in_use(email):
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        pwd = cleaned_data.get("password")
        confirm = cleaned_data.get("confirm_password")
        if pwd and confirm and pwd != confirm:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data


# ============================================================================
# 2. Login
# ============================================================================

class CustomLoginForm(AuthenticationForm):
    """Allow login with email or phone number."""

    username = forms.CharField(
        label="Email or Phone",
        widget=forms.TextInput(
            attrs={"placeholder": "Email or phone number", "autofocus": True, "class": "form-control"}
        ),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"placeholder": "Password", "class": "form-control"}
        )
    )


# ============================================================================
# 3. Client Profile & Team Management
# ============================================================================

class ClientProfileForm(forms.ModelForm):
    """
    Form for clients to edit their profile and linked organisation.
    Changing the email does NOT re-trigger verification.
    """

    company_name = forms.CharField(max_length=200, required=True)
    company_phone = forms.CharField(max_length=20, required=False)
    company_address = forms.CharField(widget=forms.Textarea, required=False)
    company_email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone_number", "physical_address"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control"}),
            "physical_address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.client_org = kwargs.pop("client_org", None)
        super().__init__(*args, **kwargs)
        if self.client_org:
            self.fields["company_name"].initial = self.client_org.name
            self.fields["company_phone"].initial = self.client_org.phone
            self.fields["company_address"].initial = self.client_org.address
            self.fields["company_email"].initial = self.client_org.email

    def clean_email(self):
        email = _normalise_email(self.cleaned_data["email"])
        validate_email_deliverable(email)
        if _email_in_use(email, exclude_pk=self.instance.pk):
            raise forms.ValidationError("Another account already uses this email.")
        return email

    def clean_company_email(self):
        email = _normalise_email(self.cleaned_data.get("company_email") or "")
        if email:
            validate_email_deliverable(email)
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
        if self.client_org:
            self.client_org.name = self.cleaned_data["company_name"]
            self.client_org.phone = self.cleaned_data["company_phone"]
            self.client_org.address = self.cleaned_data["company_address"]
            self.client_org.email = self.cleaned_data["company_email"]
            self.client_org.save()
        return user


class InviteTeamMemberForm(forms.ModelForm):
    """Invite a new user to the client organisation."""

    email = forms.EmailField()
    first_name = forms.CharField()
    last_name = forms.CharField()
    role = forms.ChoiceField(choices=User.CLIENT_ROLE_CHOICES, initial="viewer")

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "role"]

    def __init__(self, *args, **kwargs):
        self.client_org = kwargs.pop("client_org", None)
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = _normalise_email(self.cleaned_data["email"])
        validate_email_deliverable(email)
        if _email_in_use(email):
            raise forms.ValidationError("A user with this email already exists.")
        return email


# ============================================================================
# 4. 2FA Token
# ============================================================================

class TOTPTokenForm(forms.Form):
    """Simple 6-digit token input."""

    token = forms.CharField(
        label="Authenticator code",
        max_length=6,
        min_length=6,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "000000", "autocomplete": "off"}
        ),
    )


# ============================================================================
# 5. Staff User Management (Admin Panel)
# ============================================================================

class StaffUserCreationForm(UserCreationForm):
    """
    Form for creating staff users (admins only).

    `user_type`, `is_staff` and `username` are NOT user-editable here: every
    account created through this form is automatically a staff account, and the
    username is generated from the email address.
    """

    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(),
        required=False,
        help_text="Assign roles to this user",
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "is_active",
            "is_superuser",
        ]

    def clean_email(self):
        email = _normalise_email(self.cleaned_data["email"])
        validate_email_deliverable(email)
        if _email_in_use(email):
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)   # also hashes password1
        user.email = _normalise_email(user.email)
        user.username = _unique_username(user.email)
        user.user_type = "staff"            # auto-assign staff account
        user.is_staff = True
        if commit:
            user.save()
            self.save_m2m()
        return user


class StaffUserChangeForm(UserChangeForm):
    """
    Form for editing staff users. 
    Includes optional password change fields with robust validation.
    """
    
    # UserChangeForm natively includes a read-only 'password' hash field.
    # We exclude it from Meta and provide our own password1/password2 fields.
    password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "class": "form-control"}),
        required=False,
        help_text="Leave blank to keep the current password."
    )
    password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "class": "form-control"}),
        required=False,
    )
    
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(), 
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "is_active",
            "is_superuser",
        ]

    def clean_email(self):
        email = _normalise_email(self.cleaned_data["email"])
        validate_email_deliverable(email)
        if _email_in_use(email, exclude_pk=self.instance.pk):
            raise forms.ValidationError("Another account already uses this email.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = _normalise_email(user.email)
        if not user.username:
            user.username = _unique_username(user.email, exclude_pk=user.pk)
        user.user_type = "staff"            # always stays a staff account
        user.is_staff = True
        pwd = self.cleaned_data.get("password1")
        if pwd:
            user.set_password(pwd)
        if commit:
            user.save()
            self.save_m2m()
        return user

    def clean(self):
        cleaned_data = super().clean()
        pwd1 = cleaned_data.get("password1")
        pwd2 = cleaned_data.get("password2")

        # If either password field is filled, validate them
        if pwd1 or pwd2:
            if pwd1 != pwd2:
                self.add_error("password2", "The two password fields didn’t match.")
            else:
                # Run Django's built-in password validators (length, commonality, etc.)
                try:
                    validate_password(pwd1, self.instance)
                except ValidationError as e:
                    self.add_error("password1", e)
        
        return cleaned_data


# ============================================================================
# 6. Role & Permission Management
# ============================================================================

class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ["code", "name", "description"]


class PermissionForm(forms.ModelForm):
    class Meta:
        model = Permission
        fields = ["code", "description"]