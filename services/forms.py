from django import forms
from .models import Service


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'category', 'description', 'base_price', 'unit', 'is_active']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}
