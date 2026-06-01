# clients/views.py
"""
Clients App Views
-----------------
Handles listing, creation, detail, and editing of client organizations.
Access control:
- Staff (ADMIN, SALES, FINANCE) can list, create, update all clients.
- Client users can only view their own organization (if linked).
"""

from django.views.generic import ListView, CreateView, DetailView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import Http404

from core.mixins import RoleRequiredMixin
from .models import ClientOrganization, ClientContact
from .forms import ClientOrganizationForm, ClientContactForm


# =============================================================================
# Staff‑only views (with role restrictions)
# =============================================================================

class ClientListView(RoleRequiredMixin, ListView):
    """
    List all client organizations (staff only).
    Required roles: ADMIN, SALES, FINANCE.
    """
    model = ClientOrganization
    template_name = 'clients/list.html'
    context_object_name = 'clients'
    required_roles = ['ADMIN', 'SALES', 'FINANCE']
    paginate_by = 20

    def get_queryset(self):
        qs = ClientOrganization.objects.all()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q)
        return qs


class ClientCreateView(RoleRequiredMixin, CreateView):
    """
    Create a new client organization (staff only).
    Required roles: ADMIN, SALES.
    """
    model = ClientOrganization
    form_class = ClientOrganizationForm
    template_name = 'clients/form.html'
    success_url = reverse_lazy('client_list')
    required_roles = ['ADMIN', 'SALES']

    def form_valid(self, form):
        messages.success(self.request, 'Client created successfully.')
        return super().form_valid(form)


class ClientUpdateView(RoleRequiredMixin, UpdateView):
    """
    Edit an existing client organization (staff only).
    Required roles: ADMIN, SALES.
    """
    model = ClientOrganization
    form_class = ClientOrganizationForm
    template_name = 'clients/form.html'
    required_roles = ['ADMIN', 'SALES']

    def get_success_url(self):
        return reverse_lazy('client_detail', kwargs={'pk': self.object.pk})


# =============================================================================
# Client‑facing view (single organization, read‑only for clients)
# =============================================================================

class ClientDetailView(LoginRequiredMixin, DetailView):
    """
    Display a single client organization.
    - Staff: can view any organization.
    - Client: can only view their own linked organization.
    """
    model = ClientOrganization
    template_name = 'clients/detail.html'
    context_object_name = 'client'

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.user_type == 'client':
            # Client sees only their own organization
            if hasattr(user, 'client_organization'):
                return qs.filter(pk=user.client_organization.pk)
            return qs.none()
        # Staff sees all
        return qs

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Extra safety: if client tries to access another organization, raise 404
        if self.request.user.user_type == 'client':
            client_org = getattr(self.request.user, 'client_organization', None)
            if not client_org or obj.pk != client_org.pk:
                raise Http404("Organization not found.")
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['tickets'] = self.object.tickets.order_by('-created_at')[:10]
        ctx['invoices'] = self.object.invoices.order_by('-issue_date')[:10]
        ctx['contacts'] = self.object.contacts.all()
        return ctx