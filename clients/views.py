# clients/views.py
"""
Clients App Views
-----------------
Handles listing, creation, detail, editing, deletion, bulk actions, CSV export,
and client‑facing contact management.
Includes:
- Role‑based access control (staff vs client)
- Search and filters (industry, status, assigned_to)
- Pagination
- Bulk activate/deactivate/delete
- CSV export
- Client contact CRUD (for logged‑in clients)
"""

import csv

from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, Http404
from django.db.models import Q
from django.core.paginator import Paginator

from core.mixins import RoleRequiredMixin
from .models import ClientOrganization, ClientContact
from .forms import ClientOrganizationForm, ClientContactForm


# -----------------------------------------------------------------------------
# Staff‑only client management (list, create, update, delete, bulk, export)
# -----------------------------------------------------------------------------

class ClientListView(RoleRequiredMixin, ListView):
    """
    List all client organisations with search, filters, and pagination.
    Accessible only to ADMIN, SALES, FINANCE.
    """
    model = ClientOrganization
    template_name = 'clients/list.html'
    context_object_name = 'clients'
    required_roles = ['ADMIN', 'SALES', 'FINANCE']
    paginate_by = 20

    def get_queryset(self):
        qs = ClientOrganization.objects.all()
        # Search by name, email, phone, or contact name/email
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(email__icontains=q) |
                Q(phone__icontains=q) |
                Q(contacts__name__icontains=q) |
                Q(contacts__email__icontains=q)
            ).distinct()
        # Industry filter
        industry = self.request.GET.get('industry')
        if industry:
            qs = qs.filter(industry=industry)
        # Status filter
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        # Assigned to filter (if the field exists)
        assigned_to = self.request.GET.get('assigned_to')
        if assigned_to and hasattr(ClientOrganization, 'assigned_to'):
            qs = qs.filter(assigned_to_id=assigned_to)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['industry_choices'] = ClientOrganization.INDUSTRY_CHOICES
        ctx['status_choices'] = ClientOrganization.STATUS_CHOICES
        ctx['current_industry'] = self.request.GET.get('industry', '')
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['current_assigned'] = self.request.GET.get('assigned_to', '')
        # Provide list of staff users for the assigned_to filter (if field exists)
        if hasattr(ClientOrganization, 'assigned_to'):
            from accounts.models import User
            ctx['staff_users'] = User.objects.filter(user_type='staff', is_active=True)
        return ctx


class ClientCreateView(RoleRequiredMixin, CreateView):
    """Create a new client organisation (staff only)."""
    model = ClientOrganization
    form_class = ClientOrganizationForm
    template_name = 'clients/form.html'
    success_url = reverse_lazy('client_list')
    required_roles = ['ADMIN', 'SALES']


class ClientDetailView(LoginRequiredMixin, DetailView):
    """
    Display a single client organisation.
    - Staff: can view any organisation.
    - Client: can only view their own organisation.
    """
    model = ClientOrganization
    template_name = 'clients/detail.html'
    context_object_name = 'client'

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.user_type == 'client':
            # Client sees only their own organisation
            if hasattr(user, 'client_organization'):
                return qs.filter(pk=user.client_organization.pk)
            return qs.none()
        return qs

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Extra safety: if client tries to access another organisation, raise 404
        if self.request.user.user_type == 'client':
            client_org = getattr(self.request.user, 'client_organization', None)
            if not client_org or obj.pk != client_org.pk:
                raise Http404("Organisation not found.")
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['tickets'] = self.object.tickets.order_by('-created_at')[:10]
        ctx['invoices'] = self.object.invoices.order_by('-issue_date')[:10]
        ctx['contacts'] = self.object.contacts.all()
        ctx['is_staff'] = self.request.user.is_staff
        return ctx


class ClientUpdateView(RoleRequiredMixin, UpdateView):
    """Update an existing client organisation (staff only)."""
    model = ClientOrganization
    form_class = ClientOrganizationForm
    template_name = 'clients/form.html'
    required_roles = ['ADMIN', 'SALES']

    def get_success_url(self):
        return reverse_lazy('client_detail', kwargs={'pk': self.object.pk})


class ClientDeleteView(RoleRequiredMixin, DeleteView):
    """
    Delete a client organisation (staff only).
    Only inactive clients can be deleted.
    """
    model = ClientOrganization
    template_name = 'clients/client_confirm_delete.html'
    success_url = reverse_lazy('client_list')
    required_roles = ['ADMIN']

    def delete(self, request, *args, **kwargs):
        client = self.get_object()
        if client.status != 'inactive':
            messages.error(request, f"Cannot delete '{client.name}' – only inactive clients can be deleted.")
            return redirect('client_list')
        return super().delete(request, *args, **kwargs)


class ClientBulkActionView(RoleRequiredMixin, View):
    """Bulk activate, deactivate, or delete selected clients."""
    required_roles = ['ADMIN', 'SALES']

    def post(self, request):
        action = request.POST.get('action')
        client_ids = request.POST.getlist('client_ids')
        if not client_ids:
            messages.error(request, 'No clients selected.')
            return redirect('client_list')

        clients = ClientOrganization.objects.filter(pk__in=client_ids)
        if action == 'activate':
            count = clients.update(status='active')
            messages.success(request, f'{count} client(s) activated.')
        elif action == 'deactivate':
            count = clients.update(status='inactive')
            messages.success(request, f'{count} client(s) deactivated.')
        elif action == 'delete':
            # Only delete inactive clients
            deleted = 0
            for client in clients:
                if client.status == 'inactive':
                    client.delete()
                    deleted += 1
                else:
                    messages.warning(request, f"'{client.name}' not deleted – only inactive clients can be deleted.")
            messages.success(request, f'{deleted} client(s) deleted.')
        else:
            messages.error(request, 'Invalid action.')
        return redirect('client_list')


class ClientExportCSVView(RoleRequiredMixin, View):
    """Export all clients to a CSV file."""
    required_roles = ['ADMIN', 'SALES', 'FINANCE']

    def get(self, request):
        clients = ClientOrganization.objects.all()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="clients.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Industry', 'Status', 'Email', 'Phone', 'Address', 'Website', 'Created At'])
        for c in clients:
            writer.writerow([
                c.name,
                c.get_industry_display(),
                c.get_status_display(),
                c.email,
                c.phone,
                c.address,
                c.website,
                c.created_at.strftime('%Y-%m-%d %H:%M'),
            ])
        return response


# -----------------------------------------------------------------------------
# Client‑facing contact management (only for logged‑in clients)
# -----------------------------------------------------------------------------
class ClientContactListView(LoginRequiredMixin, ListView):
    model = ClientContact
    template_name = 'clients/contact_list.html'
    context_object_name = 'contacts'

    def get_queryset(self):
        client_org = getattr(self.request.user, 'client_organization', None)
        if not client_org:
            return ClientContact.objects.none()
        return ClientContact.objects.filter(client=client_org)

class ClientContactCreateView(LoginRequiredMixin, CreateView):
    """Client adds a new contact to their own organisation."""
    model = ClientContact
    form_class = ClientContactForm
    template_name = 'clients/contact_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.client_org = request.user.client_organization
        if not self.client_org:
            messages.error(request, "No client organisation linked to your account.")
            return redirect('client_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.client = self.client_org
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('client_detail', kwargs={'pk': self.client_org.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['client'] = self.client_org
        return context


class ClientContactUpdateView(LoginRequiredMixin, UpdateView):
    """Client edits an existing contact."""
    model = ClientContact
    form_class = ClientContactForm
    template_name = 'clients/contact_form.html'

    def get_queryset(self):
        client_org = self.request.user.client_organization
        if not client_org:
            return ClientContact.objects.none()
        return ClientContact.objects.filter(client=client_org)

    def get_success_url(self):
        return reverse_lazy('client_detail', kwargs={'pk': self.object.client.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['client'] = self.object.client
        return context


class ClientContactDeleteView(LoginRequiredMixin, DeleteView):
    """Client deletes a contact."""
    model = ClientContact
    template_name = 'clients/contact_confirm_delete.html'

    def get_queryset(self):
        client_org = self.request.user.client_organization
        if not client_org:
            return ClientContact.objects.none()
        return ClientContact.objects.filter(client=client_org)

    def get_success_url(self):
        return reverse_lazy('client_detail', kwargs={'pk': self.object.client.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['client'] = self.object.client
        return context