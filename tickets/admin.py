# tickets/admin.py
"""
Tickets App Admin Configuration
-------------------------------
Registers Ticket, TicketComment, TicketWorkLog, TicketAttachment, TicketSLA,
and CannedResponse models with Unfold's ModelAdmin for a modern interface.
"""

from unfold.admin import ModelAdmin
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    Ticket, TicketComment, TicketWorkLog,
    TicketAttachment, TicketSLA, CannedResponse
)


@admin.register(Ticket)
class TicketAdmin(ModelAdmin, SimpleHistoryAdmin):
    """Admin for tickets with history tracking."""
    list_display = ('ticket_number', 'title', 'client', 'status', 'priority', 'assigned_to', 'created_at')
    list_filter = ('status', 'priority', 'created_at', 'client')
    search_fields = ('ticket_number', 'title', 'client__name')
    readonly_fields = ('ticket_number', 'created_at', 'updated_at', 'history')
    fieldsets = (
        (None, {'fields': ('ticket_number', 'title', 'description')}),
        ('Relations', {'fields': ('client', 'service', 'assigned_to', 'created_by')}),
        ('Status', {'fields': ('status', 'priority')}),
        ('Dates', {'fields': ('created_at', 'updated_at', 'resolved_at')}),
        ('System', {'fields': ('history',)}),
    )
    raw_id_fields = ('client', 'service', 'assigned_to', 'created_by')


@admin.register(TicketComment)
class TicketCommentAdmin(ModelAdmin):
    list_display = ('ticket', 'author', 'is_internal', 'is_solution', 'created_at')
    list_filter = ('is_internal', 'is_solution', 'created_at')
    search_fields = ('ticket__ticket_number', 'author__email')
    raw_id_fields = ('ticket', 'author')


@admin.register(TicketWorkLog)
class TicketWorkLogAdmin(ModelAdmin):
    list_display = ('ticket', 'technician', 'hours', 'logged_at')
    list_filter = ('logged_at',)
    search_fields = ('ticket__ticket_number', 'technician__email')
    raw_id_fields = ('ticket', 'technician')


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(ModelAdmin):
    list_display = ('ticket', 'uploaded_by', 'uploaded_at', 'description')
    list_filter = ('uploaded_at',)
    search_fields = ('ticket__ticket_number', 'uploaded_by__email')
    raw_id_fields = ('ticket', 'uploaded_by')


@admin.register(TicketSLA)
class TicketSLAAdmin(ModelAdmin):
    list_display = ('ticket', 'response_due', 'resolution_due', 'breached')
    list_filter = ('breached',)
    raw_id_fields = ('ticket',)


@admin.register(CannedResponse)
class CannedResponseAdmin(ModelAdmin):
    list_display = ('title', 'is_active', 'created_by', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'content')
    raw_id_fields = ('created_by',)