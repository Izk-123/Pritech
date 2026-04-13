from django import forms
from .models import Ticket, TicketComment, TicketWorkLog, TicketAttachment


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['title', 'description', 'client', 'service', 'priority']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Brief summary of the issue'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe the issue in detail'}),
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model = TicketComment
        fields = ['content', 'is_internal']
        widgets = {'content': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Add a comment...'})}


class WorkLogForm(forms.ModelForm):
    class Meta:
        model = TicketWorkLog
        fields = ['hours', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = TicketAttachment
        fields = ['file', 'description']