"""
Portfolio App Forms
===================
- InquiryForm with honeypot spam protection.
- NewsletterForm with mandatory consent checkbox (GDPR).
"""

from django import forms
from .models import Inquiry


class InquiryForm(forms.ModelForm):
    """
    Contact inquiry form.
    Includes a hidden honeypot field to trap spam bots.
    """
    honeypot = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Inquiry
        fields = ["name", "email", "phone", "subject", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Your full name", "class": "form-control"}),
            "email": forms.EmailInput(attrs={"placeholder": "Email address", "class": "form-control"}),
            "phone": forms.TextInput(attrs={"placeholder": "Phone number (optional)", "class": "form-control"}),
            "subject": forms.TextInput(attrs={"placeholder": "How can we help?", "class": "form-control"}),
            "message": forms.Textarea(attrs={"placeholder": "Tell us more...", "rows": 4, "class": "form-control"}),
        }

    def clean_honeypot(self):
        """If honeypot field is filled, reject as spam."""
        if self.cleaned_data.get("honeypot"):
            raise forms.ValidationError("Spam detected.")
        return self.cleaned_data["honeypot"]


class NewsletterForm(forms.Form):
    """
    Newsletter subscription form with explicit consent (GDPR).
    """
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"class": "newsletter-input", "placeholder": "Your email address"}),
    )
    consent = forms.BooleanField(
        label="I agree to receive marketing emails from Pritech.",
        required=True,
        error_messages={"required": "You must consent to receive emails."},
    )