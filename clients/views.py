from django.views.generic import ListView, CreateView, DetailView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from .models import ClientOrganization, ClientContact
from .forms import ClientOrganizationForm, ClientContactForm
from core.mixins import RoleRequiredMixin


class ClientListView(RoleRequiredMixin, ListView):
    model = ClientOrganization
    template_name = 'clients/list.html'
    context_object_name = 'clients'
    required_roles = ['ADMIN', 'SALES', 'FINANCE']  # adjust as needed
    paginate_by = 20

    def get_queryset(self):
        qs = ClientOrganization.objects.all()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q)
        return qs


class ClientCreateView(RoleRequiredMixin, CreateView):
    model = ClientOrganization
    form_class = ClientOrganizationForm
    template_name = 'clients/form.html'
    success_url = reverse_lazy('client_list')
    required_roles = ['ADMIN', 'SALES']

    def form_valid(self, form):
        messages.success(self.request, 'Client created successfully.')
        return super().form_valid(form)


class ClientDetailView(LoginRequiredMixin, DetailView):
    model = ClientOrganization
    template_name = 'clients/detail.html'
    context_object_name = 'client'

    def get_queryset(self):
        """
        Staff users see all organizations.
        Client users see only their own linked organization.
        """
        qs = super().get_queryset()
        user = self.request.user
        if user.user_type == 'client':
            # Client can only view their own organization
            if hasattr(user, 'client_organization'):
                return qs.filter(pk=user.client_organization.pk)
            return qs.none()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['tickets'] = self.object.tickets.order_by('-created_at')[:10]
        ctx['invoices'] = self.object.invoices.order_by('-issue_date')[:10]
        ctx['contacts'] = self.object.contacts.all()
        return ctx


class ClientUpdateView(RoleRequiredMixin, UpdateView):
    model = ClientOrganization
    form_class = ClientOrganizationForm
    template_name = 'clients/form.html'
    required_roles = ['ADMIN', 'SALES']

    def get_success_url(self):
        return reverse_lazy('client_detail', kwargs={'pk': self.object.pk})