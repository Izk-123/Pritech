# accounts/forms.py
"""
Forms for registration, login, profile editing, staff management, and 2FA.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, UserChangeForm
from .models import Permission, User, Role, UserRole


# -----------------------------------------------------------------------------
# Client Registration (includes company_name)
# -----------------------------------------------------------------------------

class ClientRegisterForm(forms.ModelForm):
    """Client self‑registration form with organisation name."""
    company_name = forms.CharField(max_length=200, required=True, label="Company / Organisation name")
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Password', 'class': 'form-control'})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm password', 'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'physical_address',
                  'password', 'company_name']
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'First name', 'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Last name', 'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email address', 'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'placeholder': '+265 999 000 000', 'class': 'form-control'}),
            'physical_address': forms.Textarea(attrs={'placeholder': 'Your address', 'rows': 2, 'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        pwd = cleaned_data.get('password')
        confirm = cleaned_data.get('confirm_password')
        if pwd and confirm and pwd != confirm:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data


# -----------------------------------------------------------------------------
# Login Form (email or phone)
# -----------------------------------------------------------------------------

class CustomLoginForm(AuthenticationForm):
    """Allow login with email or phone number."""
    username = forms.CharField(
        label='Email or Phone',
        widget=forms.TextInput(attrs={
            'placeholder': 'Email or phone number',
            'autofocus': True,
            'class': 'form-control'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Password', 'class': 'form-control'})
    )


# -----------------------------------------------------------------------------
# Client Profile Editing (includes company fields)
# -----------------------------------------------------------------------------

class ClientProfileForm(forms.ModelForm):
    """Form for clients to edit their profile and linked organisation."""
    company_name = forms.CharField(max_length=200, required=True)
    company_phone = forms.CharField(max_length=20, required=False)
    company_address = forms.CharField(widget=forms.Textarea, required=False)
    company_email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'physical_address']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'physical_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.client_org = kwargs.pop('client_org', None)
        super().__init__(*args, **kwargs)
        if self.client_org:
            self.fields['company_name'].initial = self.client_org.name
            self.fields['company_phone'].initial = self.client_org.phone
            self.fields['company_address'].initial = self.client_org.address
            self.fields['company_email'].initial = self.client_org.email

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
        if self.client_org:
            self.client_org.name = self.cleaned_data['company_name']
            self.client_org.phone = self.cleaned_data['company_phone']
            self.client_org.address = self.cleaned_data['company_address']
            self.client_org.email = self.cleaned_data['company_email']
            self.client_org.save()
        return user


# -----------------------------------------------------------------------------
# Invite Team Member Form
# -----------------------------------------------------------------------------

class InviteTeamMemberForm(forms.ModelForm):
    """Invite a new user to the client organisation."""
    email = forms.EmailField()
    first_name = forms.CharField()
    last_name = forms.CharField()
    role = forms.ChoiceField(choices=User.CLIENT_ROLE_CHOICES, initial='viewer')

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'role']

    def __init__(self, *args, **kwargs):
        self.client_org = kwargs.pop('client_org', None)
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email


# -----------------------------------------------------------------------------
# 2FA Token Form
# -----------------------------------------------------------------------------

class TOTPTokenForm(forms.Form):
    """Simple 6‑digit token input."""
    token = forms.CharField(
        label='Authenticator code',
        max_length=6,
        min_length=6,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '000000',
            'autocomplete': 'off'
        })
    )


# -----------------------------------------------------------------------------
# Staff User Management (for admin panel)
# -----------------------------------------------------------------------------

class StaffUserCreationForm(UserCreationForm):
    """Form for creating staff users (admins only)."""
    roles = forms.ModelMultipleChoiceField(queryset=Role.objects.all(), required=False,
                                           help_text="Assign roles to this user")

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone_number', 'user_type',
                  'is_active', 'is_staff', 'is_superuser']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Restrict user_type to staff (clients are created via registration)
        self.fields['user_type'].choices = [('staff', 'Staff')]
        self.fields['user_type'].initial = 'staff'


class StaffUserChangeForm(UserChangeForm):
    """Form for editing staff users."""
    roles = forms.ModelMultipleChoiceField(queryset=Role.objects.all(), required=False)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone_number', 'user_type',
                  'is_active', 'is_staff', 'is_superuser']


# -----------------------------------------------------------------------------
# Role & Permission Forms (for staff management)
# -----------------------------------------------------------------------------

class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ['code', 'name', 'description']


class PermissionForm(forms.ModelForm):
    class Meta:
        model = Permission
        fields = ['code', 'description']