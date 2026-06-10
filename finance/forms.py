# finance/forms.py
"""
Finance App Forms
-----------------
All forms used in the finance module:
- Quotation form and inline formset
- Invoice form and inline formset
- Payment form
- Expense form
- Subscription change form
- Invoice filter form (for CSV export / filtering)
"""

from django import forms
from django.urls import reverse
from django.conf import settings

from .models import (
    Quotation, QuotationItem,
    Invoice, InvoiceItem,
    Payment,
    Expense,
    Plan, ClientSubscription,
)


# -----------------------------------------------------------------------------
# Quotation Forms
# -----------------------------------------------------------------------------
class QuotationForm(forms.ModelForm):
    """Form for creating/editing a quotation header."""

    class Meta:
        model = Quotation
        fields = ['client', 'issue_date', 'valid_until', 'notes']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-control'}),
            'issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'valid_until': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Terms, delivery notes, etc.'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['client'].required = True
        self.fields['issue_date'].required = True
        self.fields['valid_until'].required = True


class QuotationItemForm(forms.ModelForm):
    """Form for each line item in a quotation."""

    class Meta:
        model = QuotationItem
        fields = ['description', 'quantity', 'unit_price']
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Service / product'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control form-control-sm item-qty', 'step': '0.01', 'value': '1'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control form-control-sm item-price', 'step': '0.01', 'value': '0.00'}),
        }


QuotationItemFormSet = forms.inlineformset_factory(
    Quotation, QuotationItem,
    form=QuotationItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


# -----------------------------------------------------------------------------
# Invoice Forms
# -----------------------------------------------------------------------------
class InvoiceForm(forms.ModelForm):
    """Form for creating/editing an invoice header."""

    class Meta:
        model = Invoice
        fields = ['client', 'ticket', 'issue_date', 'due_date', 'notes']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-control'}),
            'ticket': forms.Select(attrs={'class': 'form-control'}),
            'issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }


class InvoiceItemForm(forms.ModelForm):
    """Form for each line item in an invoice."""

    class Meta:
        model = InvoiceItem
        fields = ['description', 'quantity', 'unit_price']
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
        }


InvoiceItemFormSet = forms.inlineformset_factory(
    Invoice, InvoiceItem,
    form=InvoiceItemForm,
    extra=1,
    can_delete=True,
)


# -----------------------------------------------------------------------------
# Payment Form
# -----------------------------------------------------------------------------
class PaymentForm(forms.ModelForm):
    """Form to record a payment against an invoice."""

    class Meta:
        model = Payment
        fields = ['amount', 'method', 'reference', 'date', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }


# -----------------------------------------------------------------------------
# Expense Form
# -----------------------------------------------------------------------------
class ExpenseForm(forms.ModelForm):
    """Form for creating a new expense (pending approval)."""

    class Meta:
        model = Expense
        fields = ['category', 'description', 'amount', 'date', 'receipt']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'receipt': forms.FileInput(attrs={'class': 'form-control'}),
        }


# -----------------------------------------------------------------------------
# Subscription Change Form (Client Portal)
# -----------------------------------------------------------------------------
class SubscriptionChangeForm(forms.ModelForm):
    """Form for client to upgrade/downgrade their subscription plan."""

    plan = forms.ModelChoiceField(
        queryset=Plan.objects.filter(is_active=True),
        label="Select Plan",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = ClientSubscription
        fields = ['plan']


# -----------------------------------------------------------------------------
# Invoice Filter Form (for list view filtering and CSV export)
# -----------------------------------------------------------------------------
class InvoiceFilterForm(forms.Form):
    """Used in invoice list view for filtering and exporting."""

    status = forms.ChoiceField(
        choices=[('', 'All statuses')] + list(Invoice.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    issue_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    issue_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    due_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    due_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )