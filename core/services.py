# core/services.py
from django.db.models import Sum, F, Q
from tickets.models import Ticket
from finance.models import Invoice
from clients.models import ClientOrganization


class CommonDashboardService:
    @staticmethod
    def get_context(user):
        """Context available to everyone (sidebar recent items)."""
        # Filter sidebar items appropriately
        if user.user_type == 'client':
            # ✅ Fixed: use 'user' field instead of 'primary_contact'
            client_org = ClientOrganization.objects.filter(user=user).first()
            if client_org:
                tickets = Ticket.objects.filter(client=client_org)
                invoices = Invoice.objects.filter(client=client_org)
            else:
                tickets = Ticket.objects.none()
                invoices = Invoice.objects.none()
        elif user.has_perm_code('view_finance_dashboard') or user.has_role('TECHNICIAN'):
            # For staff, show all recent items (or filtered by assignment)
            tickets = Ticket.objects.all()
            invoices = Invoice.objects.all()
        else:
            tickets = Ticket.objects.all()
            invoices = Invoice.objects.all()

        return {
            'recent_sidebar_tickets': tickets.order_by('-created_at')[:5],
            'recent_sidebar_invoices': invoices.order_by('-created_at')[:3],
        }


class ClientDashboardService:
    @staticmethod
    def get_context(user):
        # ✅ Fixed: use 'user' field
        client_org = ClientOrganization.objects.filter(user=user).first()
        if not client_org:
            return {}

        tickets = Ticket.objects.filter(client=client_org)
        invoices = Invoice.objects.filter(client=client_org)

        return {
            'total_tickets': tickets.count(),
            'open_tickets': tickets.exclude(status__in=['closed', 'resolved']).count(),
            'recent_tickets': tickets.order_by('-created_at')[:5],
            'recent_invoices': invoices.order_by('-created_at')[:5],
            'pending_revenue': invoices.filter(
                status__in=['issued', 'partial', 'overdue']
            ).aggregate(
                t=Sum(F('total_amount') - F('amount_paid'))
            )['t'] or 0,
            'show_finance_widgets': True,
            'show_client_widgets': True,
            'client_org': client_org,
        }


class FinanceDashboardService:
    @staticmethod
    def get_context(user):
        return {
            'total_clients': ClientOrganization.objects.filter(status='active').count(),  # ✅ fixed is_active -> status
            'revenue': Invoice.objects.filter(status='paid').aggregate(t=Sum('total_amount'))['t'] or 0,
            'pending_revenue': Invoice.objects.filter(
                status__in=['issued', 'partial', 'overdue']
            ).aggregate(t=Sum(F('total_amount') - F('amount_paid')))['t'] or 0,
            'open_tickets': Ticket.objects.exclude(status__in=['closed', 'resolved']).count(),
            'recent_tickets': Ticket.objects.order_by('-created_at')[:5],
            'recent_invoices': Invoice.objects.order_by('-created_at')[:10],
            'show_finance_widgets': True,
            'show_admin_widgets': False,
        }


class TechnicianDashboardService:
    @staticmethod
    def get_context(user):
        tickets = Ticket.objects.filter(assigned_to=user)
        return {
            'open_tickets': tickets.exclude(status__in=['closed', 'resolved']).count(),
            'recent_tickets': tickets.order_by('-created_at')[:10],
            'show_ticket_widgets': True,
            'assigned_tickets_count': tickets.count(),
        }


class AdminDashboardService:
    @staticmethod
    def get_context(user):
        return {
            'total_clients': ClientOrganization.objects.filter(status='active').count(),  # ✅ fixed is_active -> status
            'open_tickets': Ticket.objects.exclude(status__in=['closed', 'resolved']).count(),
            'revenue': Invoice.objects.filter(status='paid').aggregate(t=Sum('total_amount'))['t'] or 0,
            'pending_revenue': Invoice.objects.filter(
                status__in=['issued', 'partial', 'overdue']
            ).aggregate(t=Sum(F('total_amount') - F('amount_paid')))['t'] or 0,
            'recent_tickets': Ticket.objects.order_by('-created_at')[:10],
            'recent_invoices': Invoice.objects.order_by('-created_at')[:10],
            'ticket_stats': {
                s[0]: Ticket.objects.filter(status=s[0]).count()
                for s in Ticket.STATUS_CHOICES
            },
            'show_finance_widgets': True,
            'show_admin_widgets': True,
        }