# core/views.py
"""
Core views: main dashboard, HTMX partials, global search, audit log,
page visits, site configuration, and announcement management.
"""

from django.views.generic import TemplateView, ListView, UpdateView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.urls import reverse_lazy
from django.utils import timezone
from datetime import timedelta

from tickets.models import Ticket
from accounts.models import UserAuditLog
from tracking.models import PageVisit
from clients.models import ClientOrganization
from finance.models import Invoice, Quotation
from services.models import Service

from .models import SiteConfig, Announcement
from .services import CommonDashboardService, DashboardContextBuilder
from .forms import SiteConfigurationForm, AnnouncementForm
from .mixins import RoleRequiredMixin


# =============================================================================
# Global Search (JSON endpoint)
# =============================================================================
@require_GET
def global_search(request):
    """Search across clients, tickets, invoices, quotations, services."""
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    results = []

    clients = ClientOrganization.objects.filter(name__icontains=query)[:5]
    for c in clients:
        results.append({
            'type': 'client',
            'id': str(c.id),
            'name': c.name,
            'url': f'/clients/{c.id}/'
        })

    tickets = Ticket.objects.filter(Q(ticket_number__icontains=query) | Q(title__icontains=query))[:5]
    for t in tickets:
        results.append({
            'type': 'ticket',
            'id': t.id,
            'name': f"Ticket #{t.ticket_number}: {t.title}",
            'url': f'/tickets/{t.id}/'
        })

    invoices = Invoice.objects.filter(invoice_number__icontains=query)[:5]
    for inv in invoices:
        results.append({
            'type': 'invoice',
            'id': inv.id,
            'name': f"Invoice {inv.invoice_number}",
            'url': f'/finance/invoices/{inv.id}/'
        })

    quotations = Quotation.objects.filter(quotation_number__icontains=query)[:5]
    for q in quotations:
        results.append({
            'type': 'quotation',
            'id': q.id,
            'name': f"Quotation {q.quotation_number}",
            'url': f'/finance/quotations/{q.id}/'
        })

    services = Service.objects.filter(name__icontains=query)[:5]
    for s in services:
        results.append({
            'type': 'service',
            'id': s.id,
            'name': s.name,
            'url': f'/services/{s.id}/'
        })

    return JsonResponse({'results': results})


# =============================================================================
# Main Dashboard View
# =============================================================================
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Check maintenance mode
        config = SiteConfig.get()
        if config.maintenance_mode and not user.is_staff:
            context['maintenance_mode'] = True
            return context

        # Common sidebar context
        context.update(CommonDashboardService.get_context(user))

        # Role‑specific context (unified)
        context.update(DashboardContextBuilder.get_context(user))

        # Add online users count for staff
        if user.is_staff:
            threshold = timezone.now() - timedelta(minutes=5)
            from accounts.models import UserSession
            context['online_users_count'] = UserSession.objects.filter(
                last_activity__gte=threshold, is_active=True
            ).values('user').distinct().count()

        return context


# =============================================================================
# HTMX partial for real‑time stats (with cache control and loading indicator)
# =============================================================================
@never_cache
def core_dashboard_stats_partial(request):
    """Returns the stats cards + recent tables for HTMX polling."""
    if not request.user.is_authenticated:
        return HttpResponse(status=401)

    user = request.user
    context = DashboardContextBuilder.get_context(user)

    # Timestamp for "last updated"
    context['last_updated'] = timezone.now().strftime('%H:%M:%S')

    # site_config, announcements, and online_users_count are already supplied
    # globally via context processors (see settings.TEMPLATES), so we don't
    # need to recompute them here.

    return render(request, 'core/partials/dashboard_stats.html', context)


# =============================================================================
# Site Configuration (Super Admin only)
# =============================================================================
# core/views.py – SiteConfigurationView (updated)

class SiteConfigurationView(RoleRequiredMixin, UpdateView):
    """Display/update the singleton SiteConfig instance."""
    model = SiteConfig
    form_class = SiteConfigurationForm
    template_name = 'core/site_configuration.html'
    required_roles = ['SUPER_ADMIN', 'ADMIN']
    success_url = reverse_lazy('site_configuration')

    def get_object(self, queryset=None):
        return SiteConfig.get()

    def form_valid(self, form):
        """Handle logo clearing and replacement."""
        obj = form.save(commit=False)

        # Check if user wants to clear the logo
        clear_logo = self.request.POST.get('clear_logo') == '1'
        if clear_logo:
            # Delete existing logo file from storage
            if obj.logo:
                obj.logo.delete(save=False)
            obj.logo = None

        # Save the object (logo file will be handled automatically by form if a new file is provided)
        form.save()

        messages.success(self.request, "Site configuration updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

# Alias for symmetry with spec naming (SiteConfigurationUpdateView == SiteConfigurationView)
SiteConfigurationUpdateView = SiteConfigurationView

# =============================================================================
# Announcements (Admin)
# =============================================================================
class AnnouncementListView(RoleRequiredMixin, ListView):
    model = Announcement
    template_name = 'core/announcement_list.html'
    context_object_name = 'announcements'
    paginate_by = 25
    required_roles = ['SUPER_ADMIN', 'ADMIN']

    def get_queryset(self):
        return Announcement.objects.order_by('-start_date')


class AnnouncementCreateView(RoleRequiredMixin, CreateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = 'core/announcement_form.html'
    success_url = reverse_lazy('announcement_list')
    required_roles = ['SUPER_ADMIN', 'ADMIN']

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Announcement created successfully.")
        return response


class AnnouncementUpdateView(RoleRequiredMixin, UpdateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = 'core/announcement_form.html'
    success_url = reverse_lazy('announcement_list')
    required_roles = ['SUPER_ADMIN', 'ADMIN']

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Announcement updated successfully.")
        return response


@staff_member_required
def announcement_delete(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    if request.method == 'POST':
        announcement.delete()
        messages.success(request, "Announcement deleted.")
        return redirect('announcement_list')
    return render(request, 'core/announcement_confirm_delete.html', {'announcement': announcement})


# =============================================================================
# Admin dashboard (Unfold integration)
# =============================================================================
@staff_member_required
def admin_dashboard_view(request, extra_context=None):
    from .dashboard import dashboard_callback
    context = {}
    dashboard_callback(request, context)
    return render(request, 'admin/custom_dashboard.html', context)


# =============================================================================
# Audit Log & Page Visits
# =============================================================================
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