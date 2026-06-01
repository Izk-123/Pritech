from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import User


class ClientRegisterForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Password', 'class': 'form-control'})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm password', 'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'physical_address', 'password']
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'First name', 'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Last name', 'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email address', 'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'placeholder': '+265 999 000 000', 'class': 'form-control'}),
            'physical_address': forms.Textarea(attrs={'placeholder': 'Your address', 'rows': 2, 'class': 'form-control'}),
        }

    def clean(self):
        cd = super().clean()
        if cd.get('password') != cd.get('confirm_password'):
            raise forms.ValidationError('Passwords do not match.')
        return cd


class CustomLoginForm(AuthenticationForm):
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

class ClientProfileForm(forms.ModelForm):
    """Form for client to edit their own profile (user and organization)."""
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


class InviteTeamMemberForm(forms.ModelForm):
    """Invite a new user to the client organization."""
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
    

class TOTPTokenForm(forms.Form):
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