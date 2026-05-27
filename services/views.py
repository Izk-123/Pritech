from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal
import json
from core.mixins import RoleRequiredMixin
from .models import Service, ServiceCategory, ServicePackage
from .forms import ServiceForm, ServiceCategoryForm, ServicePackageForm
from finance.services import QuotationService


# ---------- Service Views ----------
class ServiceListView(LoginRequiredMixin, ListView):
    model = Service
    template_name = 'services/list.html'
    context_object_name = 'services'

    def get_queryset(self):
        return Service.objects.select_related('category').filter(is_active=True)


class ServiceCreateView(RoleRequiredMixin, CreateView):
    model = Service
    form_class = ServiceForm
    template_name = 'services/form.html'
    success_url = reverse_lazy('service_list')
    required_roles = ['ADMIN']


class ServiceUpdateView(RoleRequiredMixin, UpdateView):
    model = Service
    form_class = ServiceForm
    template_name = 'services/form.html'
    success_url = reverse_lazy('service_list')
    required_roles = ['ADMIN']


class ServiceDeleteView(RoleRequiredMixin, DeleteView):
    model = Service
    template_name = 'services/service_confirm_delete.html'
    success_url = reverse_lazy('service_list')
    required_roles = ['ADMIN']


# ---------- Category Views ----------
class ServiceCategoryListView(LoginRequiredMixin, ListView):
    model = ServiceCategory
    template_name = 'services/category_list.html'
    context_object_name = 'categories'


class ServiceCategoryCreateView(RoleRequiredMixin, CreateView):
    model = ServiceCategory
    form_class = ServiceCategoryForm
    template_name = 'services/category_form.html'
    success_url = reverse_lazy('service_category_list')
    required_roles = ['ADMIN']


class ServiceCategoryUpdateView(RoleRequiredMixin, UpdateView):
    model = ServiceCategory
    form_class = ServiceCategoryForm
    template_name = 'services/category_form.html'
    success_url = reverse_lazy('service_category_list')
    required_roles = ['ADMIN']


# ---------- Package Views ----------
class ServicePackageListView(LoginRequiredMixin, ListView):
    model = ServicePackage
    template_name = 'services/package_list.html'
    context_object_name = 'packages'

    def get_queryset(self):
        return ServicePackage.objects.prefetch_related('services')


class ServicePackageCreateView(RoleRequiredMixin, CreateView):
    model = ServicePackage
    form_class = ServicePackageForm
    template_name = 'services/package_form.html'
    success_url = reverse_lazy('service_package_list')
    required_roles = ['ADMIN']


class ServicePackageUpdateView(RoleRequiredMixin, UpdateView):
    model = ServicePackage
    form_class = ServicePackageForm
    template_name = 'services/package_form.html'
    success_url = reverse_lazy('service_package_list')
    required_roles = ['ADMIN']


class ServicePackageDeleteView(RoleRequiredMixin, DeleteView):
    model = ServicePackage
    template_name = 'services/package_confirm_delete.html'
    success_url = reverse_lazy('service_package_list')
    required_roles = ['ADMIN']


# ---------- Client-facing Service Catalog ----------
class ClientServiceCatalogView(LoginRequiredMixin, ListView):
    model = Service
    template_name = 'services/client_catalog.html'
    context_object_name = 'services'

    def get_queryset(self):
        return Service.objects.filter(is_active=True).select_related('category')


class RequestServiceQuoteView(LoginRequiredMixin, View):
    def get(self, request, service_pk):
        service = get_object_or_404(Service, pk=service_pk, is_active=True)
        client_org = request.user.client_organization

        if not client_org:
            messages.error(request, "Your account is not linked to a client organization. Please contact support.")
            return redirect('client_service_catalog')

        today = timezone.now().date()
        valid_until = today + timezone.timedelta(days=30)

        items_data = [{
            'description': service.name,
            'quantity': Decimal('1'),
            'unit_price': service.base_price,
        }]

        # Convert plain text note to Quill JSON
        note_text = f"Auto-generated from client request for service: {service.name}"
        note_json = json.dumps({"html": f"<p>{note_text}</p>", "delta": ""})

        quotation = QuotationService.create_quotation(
            client=client_org,
            items_data=items_data,
            issue_date=today,
            valid_until=valid_until,
            notes=note_json,
            created_by=request.user
        )

        messages.success(request, f"Quotation {quotation.quotation_number} has been created. We'll review and send it to you shortly.")
        return redirect('client_quotation_detail', pk=quotation.pk)