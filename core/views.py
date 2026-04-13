from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, F, Count
from tickets.models import Ticket
from finance.models import Invoice
from clients.models import ClientOrganization
from django.shortcuts import render
from .services import (
    ClientDashboardService,
    FinanceDashboardService,
    TechnicianDashboardService,
    AdminDashboardService,
    CommonDashboardService,
)

# class DashboardView(LoginRequiredMixin, TemplateView):
#     template_name = 'core/dashboard.html'

#     def get_context_data(self, **kwargs):
#         ctx = super().get_context_data(**kwargs)
#         ctx['total_clients'] = ClientOrganization.objects.filter(is_active=True).count()
#         ctx['open_tickets'] = Ticket.objects.exclude(status__in=['closed', 'resolved']).count()
#         ctx['total_invoices'] = Invoice.objects.count()
#         ctx['revenue'] = Invoice.objects.filter(status='paid').aggregate(t=Sum('total_amount'))['t'] or 0

#         # ✅ Fixed: use database fields with F expression
#         ctx['pending_revenue'] = Invoice.objects.filter(
#             status__in=['issued', 'partial', 'overdue']
#         ).aggregate(
#             t=Sum(F('total_amount') - F('amount_paid'))
#         )['t'] or 0

#         ctx['recent_tickets'] = Ticket.objects.select_related('client').order_by('-created_at')[:5]
#         ctx['recent_invoices'] = Invoice.objects.select_related('client').order_by('-created_at')[:5]
#         ctx['ticket_stats'] = {
#             s[0]: Ticket.objects.filter(status=s[0]).count()
#             for s in Ticket.STATUS_CHOICES
#         }
#         return ctx



class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Common context for all authenticated users
        context.update(CommonDashboardService.get_context(user))

        # Role‑specific context
        if user.user_type == 'client':
            context.update(ClientDashboardService.get_context(user))
        elif user.has_perm_code('view_finance_dashboard'):
            context.update(FinanceDashboardService.get_context(user))
        elif user.has_role('TECHNICIAN'):
            context.update(TechnicianDashboardService.get_context(user))
        else:
            # Admin / fallback
            context.update(AdminDashboardService.get_context(user))

        return context


# HTMX partial view for real‑time updates
def dashboard_stats_partial(request):
    """Return only the stats cards and recent items for HTMX polling."""
    user = request.user
    context = {}

    if user.user_type == 'client':
        context.update(ClientDashboardService.get_context(user))
    elif user.has_perm_code('view_finance_dashboard'):
        context.update(FinanceDashboardService.get_context(user))
    elif user.has_role('TECHNICIAN'):
        context.update(TechnicianDashboardService.get_context(user))
    else:
        context.update(AdminDashboardService.get_context(user))

    # Add site_config for currency symbol, etc.
    from core.context_processors import site_config
    context['site_config'] = site_config(request)['site_config']

    return render(request, 'core/partials/dashboard_stats.html', context)

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from accounts.models import UserAuditLog
from tracking.models import PageVisit


class AuditLogView(LoginRequiredMixin, ListView):
    model = UserAuditLog
    template_name = 'core/audit_log.html'
    context_object_name = 'logs'
    paginate_by = 50

    def get_queryset(self):
        return UserAuditLog.objects.select_related('user').order_by('-timestamp')


class PageVisitView(LoginRequiredMixin, ListView):
    model = PageVisit
    template_name = 'core/page_visits.html'
    context_object_name = 'visits'
    paginate_by = 50

    def get_queryset(self):
        return PageVisit.objects.select_related('user').order_by('-timestamp')
