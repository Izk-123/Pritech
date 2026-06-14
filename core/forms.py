# core/forms.py
"""
Forms for the Core app: Site Configuration, Announcements,
and per-user Dashboard Preferences.
"""

from django import forms
from .models import SiteConfig, Announcement, DashboardWidget


class SiteConfigurationForm(forms.ModelForm):
    """Edit company-wide settings and branding (Super Admin only)."""

    class Meta:
        model = SiteConfig
        fields = [
            'company_name', 'tagline', 'logo',
            'email', 'phone', 'address', 'website',
            'vat_rate', 'currency', 'currency_symbol',
            'bank_name', 'bank_account', 'mobile_money',
            'invoice_footer', 'maintenance_mode',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'invoice_footer': forms.Textarea(attrs={'rows': 3}),
            'tagline': forms.TextInput(attrs={'placeholder': 'Company slogan / tagline'}),
        }

    def clean_vat_rate(self):
        rate = self.cleaned_data['vat_rate']
        if rate < 0 or rate > 1:
            raise forms.ValidationError("VAT rate must be expressed as a decimal between 0 and 1 (e.g. 0.175 for 17.5%).")
        return rate


class AnnouncementForm(forms.ModelForm):
    """Create/edit a system-wide announcement."""

    class Meta:
        model = Announcement
        fields = ['title', 'message', 'start_date', 'end_date', 'is_active']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 4}),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure datetime-local inputs render existing values correctly
        self.fields['start_date'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['end_date'].input_formats = ['%Y-%m-%dT%H:%M']

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        if start and end and end <= start:
            raise forms.ValidationError("End date must be after the start date.")
        return cleaned_data


class DashboardPreferenceForm(forms.Form):
    """
    Per-user dashboard widget visibility/ordering preferences.
    Renders a checkbox per active DashboardWidget the user is allowed to see.
    """

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        widgets_qs = DashboardWidget.objects.filter(is_active=True)
        if user is not None:
            # Show widgets with no role restriction, or matching the user's roles
            user_roles = getattr(user, 'roles', None)
            if user_roles is not None:
                widgets_qs = widgets_qs.filter(
                    forms.models.Q(roles__isnull=True) | forms.models.Q(roles__in=user_roles.all())
                ).distinct()

        for widget in widgets_qs:
            field_name = f'widget_{widget.code}'
            self.fields[field_name] = forms.BooleanField(
                label=widget.name,
                required=False,
                initial=True,
                help_text=widget.description,
            )

    def get_visible_widget_codes(self):
        """Return the list of widget codes the user has enabled."""
        return [
            name.replace('widget_', '', 1)
            for name, value in self.cleaned_data.items()
            if name.startswith('widget_') and value
        ]