# tickets/urls.py
"""
Tickets App URL Configuration
-----------------------------
Defines all endpoints for ticket management, including list, create, detail,
status transitions, assignments, comments, work logs, attachments, bulk actions,
and marking a comment as solution.
"""

from django.urls import path
from .views import (
    TicketListView, TicketCreateView, TicketDetailView,
    TicketTransitionView, AssignTicketView,
    AddCommentView, AddWorkLogView, AddAttachmentView,
    BulkTicketActionView, MarkSolutionView
)

urlpatterns = [
    # Ticket listing and creation
    path('', TicketListView.as_view(), name='ticket_list'),
    path('new/', TicketCreateView.as_view(), name='ticket_create'),

    # Ticket detail and actions
    path('<int:pk>/', TicketDetailView.as_view(), name='ticket_detail'),
    path('<int:pk>/transition/', TicketTransitionView.as_view(), name='ticket_transition'),
    path('<int:pk>/assign/', AssignTicketView.as_view(), name='ticket_assign'),

    # Comments, work logs, attachments (HTMX endpoints)
    path('<int:pk>/comment/', AddCommentView.as_view(), name='ticket_comment'),
    path('<int:pk>/worklog/', AddWorkLogView.as_view(), name='ticket_worklog'),
    path('<int:pk>/attachment/', AddAttachmentView.as_view(), name='ticket_attachment'),

    # Mark a comment as the solution (staff only)
    path('<int:pk>/comments/<int:comment_id>/mark-solution/', MarkSolutionView.as_view(), name='mark_solution'),

    # Bulk actions (close multiple tickets)
    path('bulk-action/', BulkTicketActionView.as_view(), name='ticket_bulk_action'),
]