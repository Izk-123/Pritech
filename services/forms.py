# services/forms.py
from django import forms
from decimal import Decimal
from .models import Service, ServiceCategory, ServicePackage, ServiceRequest

# Predefined icon choices
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


# -----------------------------------------------------------------------------
# Custom widget: adds data-price attribute to each service checkbox
# -----------------------------------------------------------------------------
class ServiceCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    """
    Custom CheckboxSelectMultiple widget that adds a 'data-price' attribute
    to each checkbox option, containing the service's base_price.
    """
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        # `value` may be a ModelChoiceIteratorValue (a wrapper around the pk).
        # Convert it to a plain integer for database lookup.
        try:
            # Extract the actual primary key integer
            pk = int(value) if value is not None else None
            if pk:
                # Use only() to fetch just the needed field (performance)
                service = Service.objects.only('base_price').get(pk=pk)
                option['attrs']['data-price'] = str(service.base_price)
        except (TypeError, ValueError, Service.DoesNotExist):
            # If anything fails, simply omit the data-price attribute
            pass
        return option


# -----------------------------------------------------------------------------
# Service Form
# -----------------------------------------------------------------------------
class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'category', 'description', 'base_price', 'unit', 'billing_type', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Network Installation',
                'autocomplete': 'off'
            }),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Describe what this service includes...'
            }),
            'base_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'unit': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., job, hour, month, project'
            }),
            'billing_type': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }
        labels = {
            'name': 'Service Name',
            'base_price': 'Base Price',
            'unit': 'Billing Unit',
            'billing_type': 'Billing Type',
            'is_active': 'Active (visible to clients)',
        }
        help_texts = {
            'name': 'Unique name for this service.',
            'unit': 'How the service is measured (job, hour, month).',
            'billing_type': 'One‑time or recurring charge.',
            'is_active': 'Inactive services are hidden from the client catalog.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field.widget.__class__ in [forms.TextInput, forms.NumberInput, forms.Textarea]:
                field.widget.attrs.setdefault('placeholder', field.label)


# -----------------------------------------------------------------------------
# Service Category Form
# -----------------------------------------------------------------------------
class ServiceCategoryForm(forms.ModelForm):
    icon = forms.ChoiceField(
        choices=ICON_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = ServiceCategory
        fields = ['name', 'icon', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Networking',
                'autocomplete': 'off'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Describe what this category covers...'
            }),
        }
        labels = {'name': 'Category Name'}
        help_texts = {
            'name': 'A short, descriptive name for the category.',
            'icon': 'Choose an icon that represents this category.',
            'description': 'Optional description (appears in the admin and category list).',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].widget.attrs.setdefault('placeholder', 'Brief description of this category...')


# -----------------------------------------------------------------------------
# Service Package Form
# -----------------------------------------------------------------------------
class ServicePackageForm(forms.ModelForm):
    class Meta:
        model = ServicePackage
        fields = ['name', 'description', 'services', 'monthly_price', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Business Pro Package',
                'autocomplete': 'off'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Describe what this package includes and its benefits...'
            }),
            'services': ServiceCheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
            'monthly_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }
        labels = {
            'name': 'Package Name',
            'monthly_price': 'Monthly Price',
            'is_active': 'Active (visible to clients)',
        }
        help_texts = {
            'name': 'Unique name for this package.',
            'services': 'Select the services to include in this bundle.',
            'monthly_price': 'Fixed monthly price for the entire package.',
            'is_active': 'Inactive packages are hidden from the client catalog.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].widget.attrs.setdefault('placeholder', 'Describe the package contents and value proposition.')

    def clean(self):
        cleaned_data = super().clean()
        monthly_price = cleaned_data.get('monthly_price')
        services = cleaned_data.get('services')

        if not services:
            raise forms.ValidationError("A package must contain at least one service.")

        if monthly_price and services:
            total = sum(s.base_price for s in services)
            if monthly_price < total * Decimal('0.9') or monthly_price > total * Decimal('1.1'):
                raise forms.ValidationError(
                    f"Package price ({monthly_price}) should be within 10% of sum of service prices ({total}). "
                    f"Current total is {total}. Adjust the price or services."
                )
        return cleaned_data


# -----------------------------------------------------------------------------
# Service Request Form (client-facing)
# -----------------------------------------------------------------------------
class ServiceRequestForm(forms.ModelForm):
    class Meta:
        model = ServiceRequest
        fields = ['service', 'description']
        widgets = {
            'service': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Please provide any specific requirements, deadlines, or questions...'
            }),
        }
        labels = {
            'service': 'Service',
            'description': 'Additional Information',
        }
        help_texts = {
            'service': 'Select the service you are interested in.',
            'description': 'Tell us more about your needs (optional but recommended).',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service'].queryset = Service.objects.filter(is_active=True)
        self.fields['service'].empty_label = "Select a service..."
        self.fields['description'].widget.attrs.setdefault('placeholder', 'e.g., We need installation by next Friday, 10 workstations...')