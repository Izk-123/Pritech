from django.contrib import admin
from .models import Ticket, TicketComment, TicketWorkLog, TicketAttachment, TicketSLA

class CommentInline(admin.TabularInline):
    model = TicketComment
    extra = 0

class AttachmentInline(admin.TabularInline):
    model = TicketAttachment
    extra = 0

class SLAInline(admin.StackedInline):
    model = TicketSLA
    can_delete = False

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'title', 'client', 'status', 'priority', 'assigned_to', 'created_at')
    list_filter = ('status', 'priority')
    search_fields = ('ticket_number', 'title', 'description')
    inlines = [CommentInline, AttachmentInline, SLAInline]

@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'uploaded_by', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('ticket__ticket_number', 'description')

@admin.register(TicketSLA)
class TicketSLAAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'response_due', 'resolution_due', 'breached')
    list_filter = ('breached',)