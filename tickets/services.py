from django.utils import timezone
from .models import Ticket, TicketComment, TicketWorkLog
from infrastructure.notifications import notify_ticket_created, notify_ticket_status_changed


class TicketService:
    @staticmethod
    def create_ticket(title, description, client, service=None, priority='medium', created_by=None):
        return Ticket.objects.create(
            title=title, description=description, client=client,
            service=service, priority=priority, created_by=created_by, status='open'
        )

    @staticmethod
    def transition(ticket, new_status, user=None, note=''):
        if not ticket.can_transition_to(new_status):
            raise ValueError(f'Cannot move ticket from {ticket.status} to {new_status}')
        old = ticket.status
        ticket.status = new_status
        if new_status == 'resolved':
            ticket.resolved_at = timezone.now()
        ticket.save(update_fields=['status', 'resolved_at', 'updated_at'])
        if note or user:
            TicketComment.objects.create(
                ticket=ticket, author=user,
                content=note or f'Status changed from {old} to {new_status}',
                is_internal=True
            )
        notify_ticket_status_changed(ticket, old, user)
        return ticket

    @staticmethod
    def assign(ticket, technician, user=None):
        ticket.assigned_to = technician
        if ticket.status == 'open':
            ticket.status = 'assigned'
        ticket.save(update_fields=['assigned_to', 'status', 'updated_at'])
        TicketComment.objects.create(
            ticket=ticket, author=user,
            content=f'Assigned to {technician.get_full_name() or technician.email}',
            is_internal=True
        )

    @staticmethod
    def log_work(ticket, technician, hours, description):
        return TicketWorkLog.objects.create(
            ticket=ticket, technician=technician,
            hours=hours, description=description
        )
