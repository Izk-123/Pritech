# core/services.py
"""
Dashboard context builders with caching.
Role‑specific data for the main dashboard.
"""

import logging
from django.core.cache import cache
from django.db.models import Sum, F
from tickets.models import Ticket
from finance.models import Invoice
from clients.models import ClientOrganization

logger = logging.getLogger(__name__)

# Cache timeout for dashboard aggregates (seconds)
DASHBOARD_CACHE_TIMEOUT = 60  # 1 minute


class DashboardContextBuilder:
    """Unified builder for role‑specific dashboard context with caching."""

    @staticmethod
    def get_context(user):
        """Main entry point – returns context dict for the given user."""
        if user.user_type == 'client':
            return ClientDashboardService.get_context(user)
        elif user.has_perm_code('view_finance_dashboard'):
            return FinanceDashboardService.get_context(user)
        elif user.has_role('TECHNICIAN'):
            return TechnicianDashboardService.get_context(user)
        else:
            return AdminDashboardService.get_context(user)


class CommonDashboardService:
    """Sidebar recent items (no caching – these are lightweight)."""

    @staticmethod
    def get_context(user):
        if user.user_type == 'client':
            # FIXED: use the ForeignKey on User, not the old OneToOne reverse
            client_org = user.client_organization
            if client_org:
                tickets = Ticket.objects.filter(client=client_org)
                invoices = Invoice.objects.filter(client=client_org)
            else:
                tickets = Ticket.objects.none()
                invoices = Invoice.objects.none()
        elif user.has_perm_code('view_finance_dashboard') or user.has_role('TECHNICIAN'):
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
        # FIXED: use the ForeignKey on User
        client_org = user.client_organization
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
            ).aggregate(t=Sum(F('total_amount') - F('amount_paid')))['t'] or 0,
            'show_finance_widgets': True,
            'show_client_widgets': True,
            'client_org': client_org,
        }


class FinanceDashboardService:
    @staticmethod
    def get_context(user):
        cache_key = 'dashboard_finance_aggregates'
        aggregates = cache.get(cache_key)
        if aggregates is None:
            try:
                aggregates = {
                    'total_clients': ClientOrganization.objects.filter(status='active').count(),
                    'revenue': Invoice.objects.filter(status='paid').aggregate(t=Sum('total_amount'))['t'] or 0,
                    'pending_revenue': Invoice.objects.filter(
                        status__in=['issued', 'partial', 'overdue']
                    ).aggregate(t=Sum(F('total_amount') - F('amount_paid')))['t'] or 0,
                    'open_tickets': Ticket.objects.exclude(status__in=['closed', 'resolved']).count(),
                }
                cache.set(cache_key, aggregates, DASHBOARD_CACHE_TIMEOUT)
            except Exception as e:
                logger.error(f"Failed to compute finance aggregates: {e}")
                aggregates = {
                    'total_clients': 0,
                    'revenue': 0,
                    'pending_revenue': 0,
                    'open_tickets': 0,
                }

        recent_tickets = Ticket.objects.order_by('-created_at')[:5]
        recent_invoices = Invoice.objects.order_by('-created_at')[:10]

        return {
            'total_clients': aggregates['total_clients'],
            'revenue': aggregates['revenue'],
            'pending_revenue': aggregates['pending_revenue'],
            'open_tickets': aggregates['open_tickets'],
            'recent_tickets': recent_tickets,
            'recent_invoices': recent_invoices,
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
        cache_key = 'dashboard_admin_aggregates'
        aggregates = cache.get(cache_key)
        if aggregates is None:
            try:
                aggregates = {
                    'total_clients': ClientOrganization.objects.filter(status='active').count(),
                    'open_tickets': Ticket.objects.exclude(status__in=['closed', 'resolved']).count(),
                    'revenue': Invoice.objects.filter(status='paid').aggregate(t=Sum('total_amount'))['t'] or 0,
                    'pending_revenue': Invoice.objects.filter(
                        status__in=['issued', 'partial', 'overdue']
                    ).aggregate(t=Sum(F('total_amount') - F('amount_paid')))['t'] or 0,
                }
                cache.set(cache_key, aggregates, DASHBOARD_CACHE_TIMEOUT)
            except Exception as e:
                logger.error(f"Failed to compute admin aggregates: {e}")
                aggregates = {
                    'total_clients': 0,
                    'open_tickets': 0,
                    'revenue': 0,
                    'pending_revenue': 0,
                }

        recent_tickets = Ticket.objects.order_by('-created_at')[:10]
        recent_invoices = Invoice.objects.order_by('-created_at')[:10]

        ticket_stats = {
            s[0]: Ticket.objects.filter(status=s[0]).count()
            for s in Ticket.STATUS_CHOICES
        }

        return {
            'total_clients': aggregates['total_clients'],
            'open_tickets': aggregates['open_tickets'],
            'revenue': aggregates['revenue'],
            'pending_revenue': aggregates['pending_revenue'],
            'recent_tickets': recent_tickets,
            'recent_invoices': recent_invoices,
            'ticket_stats': ticket_stats,
            'show_finance_widgets': True,
            'show_admin_widgets': True,
        }