# tickets/services.py
import json
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.sites.models import Site

from .models import Ticket, TicketComment, TicketWorkLog, TicketSLA, CannedResponse
from core.models import SiteConfig


class TicketService:
    @staticmethod
    def _ensure_quill_json(value):
        if value is None:
            return None
        if isinstance(value, str) and not value.strip().startswith('{'):
            return json.dumps({"html": f"<p>{value}</p>", "delta": ""})
        return value

    @staticmethod
    def create_ticket(title, description, client, service=None, priority='medium', created_by=None):
        description_json = TicketService._ensure_quill_json(description)
        ticket = Ticket.objects.create(
            title=title,
            description=description_json,
            client=client,
            service=service,
            priority=priority,
            created_by=created_by,
            status='open'
        )
        TicketService.create_sla(ticket)
        TicketService.notify_ticket_created(ticket)
        return ticket

    @staticmethod
    def create_sla(ticket):
        hours_map = {
            'low': 48,
            'medium': 24,
            'high': 8,
            'critical': 4,
        }
        now = timezone.now()
        response_hours = hours_map.get(ticket.priority, 24)
        resolution_hours = response_hours * 4
        response_due = now + timedelta(hours=response_hours)
        resolution_due = now + timedelta(hours=resolution_hours)
        return TicketSLA.objects.create(
            ticket=ticket,
            response_due=response_due,
            resolution_due=resolution_due,
            breached=False
        )

    @staticmethod
    def update_sla(ticket):
        """Recalculate SLA due dates based on current priority."""
        if not hasattr(ticket, 'sla'):
            return
        hours_map = {'low': 48, 'medium': 24, 'high': 8, 'critical': 4}
        hours = hours_map.get(ticket.priority, 24)
        resolution_hours = hours * 4
        now = timezone.now()
        ticket.sla.response_due = now + timedelta(hours=hours)
        ticket.sla.resolution_due = now + timedelta(hours=resolution_hours)
        ticket.sla.breached = False
        ticket.sla.save()

    @staticmethod
    def transition(ticket, new_status, user=None, note=''):
        if not ticket.can_transition_to(new_status):
            raise ValueError(f'Cannot move ticket from {ticket.status} to {new_status}')
        old_status = ticket.status
        old_priority = ticket.priority
        ticket.status = new_status
        if new_status == 'resolved':
            ticket.resolved_at = timezone.now()
        ticket.save(update_fields=['status', 'resolved_at', 'updated_at'])

        # If priority changed during transition, update SLA
        if ticket.priority != old_priority and hasattr(ticket, 'sla'):
            TicketService.update_sla(ticket)

        if note or user:
            note_json = TicketService._ensure_quill_json(note or f'Status changed from {old_status} to {new_status}')
            TicketComment.objects.create(
                ticket=ticket, author=user,
                content=note_json,
                is_internal=True
            )
        TicketService.notify_ticket_status_changed(ticket, old_status, user)
        return ticket

    @staticmethod
    def assign(ticket, technician, user=None):
        ticket.assigned_to = technician
        if ticket.status == 'open':
            ticket.status = 'assigned'
        ticket.save(update_fields=['assigned_to', 'status', 'updated_at'])
        comment_content = f'Assigned to {technician.get_full_name() or technician.email}'
        comment_json = TicketService._ensure_quill_json(comment_content)
        TicketComment.objects.create(
            ticket=ticket, author=user,
            content=comment_json,
            is_internal=True
        )

    @staticmethod
    def log_work(ticket, technician, hours, description):
        description_json = TicketService._ensure_quill_json(description)
        return TicketWorkLog.objects.create(
            ticket=ticket, technician=technician,
            hours=hours, description=description_json
        )

    # --- Email notifications ---
    @staticmethod
    def notify_ticket_created(ticket):
        config = SiteConfig.get()
        subject = f"New Ticket: {ticket.ticket_number} - {ticket.title}"
        context = {'ticket': ticket, 'site_url': Site.objects.get_current().domain}
        message = render_to_string('tickets/emails/ticket_created.txt', context)
        html_message = render_to_string('tickets/emails/ticket_created.html', context)
        recipients = [ticket.client.email]
        if ticket.assigned_to:
            recipients.append(ticket.assigned_to.email)
        send_mail(subject, message, config.email, recipients, html_message=html_message, fail_silently=True)

    @staticmethod
    def notify_ticket_status_changed(ticket, old_status, user):
        config = SiteConfig.get()
        subject = f"Ticket {ticket.ticket_number} status changed to {ticket.get_status_display()}"
        context = {'ticket': ticket, 'old_status': old_status, 'changed_by': user}
        message = render_to_string('tickets/emails/status_changed.txt', context)
        html_message = render_to_string('tickets/emails/status_changed.html', context)
        recipients = [ticket.client.email]
        if ticket.assigned_to:
            recipients.append(ticket.assigned_to.email)
        send_mail(subject, message, config.email, recipients, html_message=html_message, fail_silently=True)