from django import forms
from .models import Invoice, InvoiceItem, Payment, Expense, Quotation, QuotationItem


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['client', 'ticket', 'issue_date', 'due_date', 'notes']
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ['description', 'quantity', 'unit_price']


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount', 'method', 'reference', 'date', 'notes']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['category', 'description', 'amount', 'date', 'receipt']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}

class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = ['client', 'issue_date', 'valid_until', 'notes']
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'valid_until': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

class QuotationItemForm(forms.ModelForm):
    class Meta:
        model = QuotationItem
        fields = ['description', 'quantity', 'unit_price']

# For handling multiple items in one form
QuotationItemFormSet = forms.inlineformset_factory(
    Quotation, QuotationItem, form=QuotationItemForm,
    extra=1, can_delete=True
)