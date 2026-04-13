from django import forms
from .models import Service, ServiceCategory, ServicePackage


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = [
            'name', 'category', 'description',
            'base_price', 'unit', 'billing_type', 'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class ServiceCategoryForm(forms.ModelForm):
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