from django import forms
from .models import Inquiry


class InquiryForm(forms.ModelForm):
    class Meta:
        model = Inquiry
        fields = ['name', 'email', 'phone', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Your full name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email address'}),
            'phone': forms.TextInput(attrs={'placeholder': 'Phone number'}),
            'subject': forms.TextInput(attrs={'placeholder': 'How can we help?'}),
            'message': forms.Textarea(attrs={'placeholder': 'Tell us more...', 'rows': 4}),
        }
