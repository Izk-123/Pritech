from django.contrib import admin
from .models import Ticket, TicketComment, TicketWorkLog

class CommentInline(admin.TabularInline):
    model = TicketComment
    extra = 0

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'client', 'status', 'priority', 'assigned_to', 'created_at')
    list_filter = ('status', 'priority')
    search_fields = ('title', 'description')
    inlines = [CommentInline]
