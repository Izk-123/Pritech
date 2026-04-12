from django import forms
from .models import ClientOrganization, ClientContact


class ClientOrganizationForm(forms.ModelForm):
    class Meta:
        model = ClientOrganization
        fields = ['name', 'industry', 'registration_number', 'email', 'phone', 'address', 'website', 'notes']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class ClientContactForm(forms.ModelForm):
    class Meta:
        model = ClientContact
        fields = ['name', 'role', 'email', 'phone', 'is_primary']
