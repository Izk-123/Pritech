from django.utils import timezone
from datetime import timedelta
from .models import Ticket, TicketComment, TicketWorkLog, TicketSLA
from infrastructure.notifications import notify_ticket_created, notify_ticket_status_changed


class TicketService:
    @staticmethod
    def create_ticket(title, description, client, service=None, priority='medium', created_by=None):
        ticket = Ticket.objects.create(
            title=title, description=description, client=client,
            service=service, priority=priority, created_by=created_by, status='open'
        )
        # Create SLA record
        TicketService.create_sla(ticket)
        return ticket

    @staticmethod
    def create_sla(ticket):
        """Calculate SLA deadlines based on priority."""
        # Hours mapping: response time = resolution time / 4 (example)
        hours_map = {
            'low': 48,
            'medium': 24,
            'high': 8,
            'critical': 4,
        }
        now = timezone.now()
        response_hours = hours_map.get(ticket.priority, 24)
        resolution_hours = response_hours * 4   # e.g., critical: 4h response, 16h resolution

        response_due = now + timedelta(hours=response_hours)
        resolution_due = now + timedelta(hours=resolution_hours)

        return TicketSLA.objects.create(
            ticket=ticket,
            response_due=response_due,
            resolution_due=resolution_due,
            breached=False
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
        