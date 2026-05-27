from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline, StackedInline
from .models import Ticket, TicketComment, TicketAttachment, TicketSLA, TicketWorkLog


class CommentInline(TabularInline):
    model = TicketComment
    extra = 0
    fields = ('author', 'content', 'is_internal', 'created_at')
    readonly_fields = ('created_at',)


class AttachmentInline(TabularInline):
    model = TicketAttachment
    extra = 0
    fields = ('file', 'description', 'uploaded_by', 'uploaded_at')
    readonly_fields = ('uploaded_at',)


class SLAInline(StackedInline):
    model = TicketSLA
    can_delete = False
    fields = ('response_due', 'resolution_due', 'breached')
    readonly_fields = ('response_due', 'resolution_due')


@admin.register(Ticket)
class TicketAdmin(ModelAdmin):
    list_display = ('ticket_number', 'title', 'client', 'status', 'priority', 'assigned_to', 'created_at')
    list_filter = ('status', 'priority', 'created_at')
    search_fields = ('ticket_number', 'title', 'description')
    readonly_fields = ('ticket_number', 'created_at', 'updated_at', 'resolved_at')
    inlines = [CommentInline, AttachmentInline, SLAInline]

    fieldsets = (
        (None, {'fields': ('ticket_number', 'title', 'description', 'client', 'service')}),
        ('Assignment & Workflow', {'fields': ('assigned_to', 'status', 'priority')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at', 'resolved_at'), 'classes': ('collapse',)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('client', 'assigned_to')


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(ModelAdmin):
    list_display = ('id', 'ticket', 'uploaded_by', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('ticket__ticket_number', 'description')
    readonly_fields = ('uploaded_at',)


@admin.register(TicketSLA)
class TicketSLAAdmin(ModelAdmin):
    list_display = ('ticket', 'response_due', 'resolution_due', 'breached')
    list_filter = ('breached',)
    readonly_fields = ('ticket', 'response_due', 'resolution_due')


@admin.register(TicketWorkLog)
class TicketWorkLogAdmin(ModelAdmin):
    list_display = ('ticket', 'technician', 'hours', 'logged_at')
    list_filter = ('logged_at',)
    search_fields = ('ticket__ticket_number', 'technician__email')
    readonly_fields = ('logged_at',)