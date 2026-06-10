# services/forms.py
from django import forms
from decimal import Decimal
from .models import Service, ServiceCategory, ServicePackage

# Predefined icon choices (low‑risk improvement)
ICON_CHOICES = [
    ('🔧', '🔧 Tools'),
    ('🌐', '🌐 Networking'),
    ('🖥', '🖥 Hardware'),
    ('💻', '💻 Software'),
    ('🔒', '🔒 Security'),
    ('🎓', '🎓 Training'),
    ('📡', '📡 Connectivity'),
    ('☁', '☁ Cloud'),
    ('📞', '📞 Support'),
    ('📦', '📦 Package'),
]


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'category', 'description', 'base_price', 'unit', 'billing_type', 'is_active']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}


class ServiceCategoryForm(forms.ModelForm):
    """Category form with predefined icon dropdown."""
    icon = forms.ChoiceField(choices=ICON_CHOICES, required=False,
                             widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = ServiceCategory
        fields = ['name', 'icon', 'description']


class ServicePackageForm(forms.ModelForm):
    class Meta:
        model = ServicePackage
        fields = ['name', 'description', 'services', 'monthly_price', 'is_active']
        widgets = {
            'services': forms.CheckboxSelectMultiple(),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        monthly_price = cleaned_data.get('monthly_price')
        services = cleaned_data.get('services')
        if monthly_price and services:
            total = sum(s.base_price for s in services)
            # Allow ±10% tolerance for bundling discounts
            if monthly_price < total * Decimal('0.9') or monthly_price > total * Decimal('1.1'):
                raise forms.ValidationError(
                    f"Package price ({monthly_price}) should be within 10% of sum of service prices ({total}). "
                    f"Current total is {total}. Adjust the price or services."
                )
        return cleaned_data