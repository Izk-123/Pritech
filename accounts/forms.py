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
