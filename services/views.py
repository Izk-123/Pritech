# services/views.py
"""
Services App Views
------------------
Handles service catalogue (staff and client), categories, packages,
quotation requests, bulk actions, search, CSV export, and caching.
"""

import csv
import json
from decimal import Decimal

from django.core.cache import cache
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.db.models import Q
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone

from core.mixins import RoleRequiredMixin
from .models import Service, ServiceCategory, ServicePackage
from .forms import ServiceForm, ServiceCategoryForm, ServicePackageForm
from finance.services import QuotationService


# -----------------------------------------------------------------------------
# Staff‑only Service Management (with search & bulk actions)
# -----------------------------------------------------------------------------

class ServiceListView(RoleRequiredMixin, ListView):
    """
    List all services (staff only).
    Supports search by name or category, and pagination.
    """
    model = Service
    template_name = 'services/list.html'
    context_object_name = 'services'
    required_roles = ['ADMIN', 'SALES', 'FINANCE']
    paginate_by = 20

    def get_queryset(self):
        qs = Service.objects.select_related('category')
        search = self.request.GET.get('q')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(category__name__icontains=search)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_query'] = self.request.GET.get('q', '')
        return ctx


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


class ServiceBulkActionView(RoleRequiredMixin, View):
    """Bulk activate/deactivate services."""
    required_roles = ['ADMIN']

    def post(self, request):
        action = request.POST.get('action')
        service_ids = request.POST.getlist('service_ids')
        if not service_ids:
            messages.error(request, 'No services selected.')
            return redirect('service_list')

        services = Service.objects.filter(pk__in=service_ids)
        if action == 'activate':
            count = services.update(is_active=True)
            messages.success(request, f'{count} service(s) activated.')
        elif action == 'deactivate':
            count = services.update(is_active=False)
            messages.success(request, f'{count} service(s) deactivated.')
        else:
            messages.error(request, 'Invalid action.')
        return redirect('service_list')


class ServiceExportCSVView(RoleRequiredMixin, View):
    """Export all services to CSV file."""
    required_roles = ['ADMIN', 'FINANCE', 'SALES']

    def get(self, request):
        services = Service.objects.select_related('category')
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="services.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Category', 'Base Price', 'Unit', 'Billing Type', 'Active', 'Created At'])
        for s in services:
            writer.writerow([
                s.name,
                s.category.name if s.category else '',
                s.base_price,
                s.unit,
                s.get_billing_type_display(),
                'Yes' if s.is_active else 'No',
                s.created_at.strftime('%Y-%m-%d %H:%M'),
            ])
        return response


# -----------------------------------------------------------------------------
# Service Categories (Staff only, with pagination)
# -----------------------------------------------------------------------------

class ServiceCategoryListView(LoginRequiredMixin, ListView):
    model = ServiceCategory
    template_name = 'services/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20


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


# -----------------------------------------------------------------------------
# Service Packages (Staff only, with deletion protection)
# -----------------------------------------------------------------------------

class ServicePackageListView(LoginRequiredMixin, ListView):
    model = ServicePackage
    template_name = 'services/package_list.html'
    context_object_name = 'packages'
    paginate_by = 20

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

    def delete(self, request, *args, **kwargs):
        package = self.get_object()
        # Prevent deletion if package is referenced in active subscriptions
        from finance.models import ClientSubscription
        if ClientSubscription.objects.filter(plan__name=package.name).exists():
            messages.error(
                request,
                f"Cannot delete package '{package.name}' because it is used in active subscriptions."
            )
            return redirect('service_package_list')
        return super().delete(request, *args, **kwargs)


# -----------------------------------------------------------------------------
# Client‑Facing Service Catalog (with caching, pagination, packages)
# -----------------------------------------------------------------------------

class ClientServiceCatalogView(LoginRequiredMixin, ListView):
    """
    Public catalog for clients to browse active services and packages.
    Cached for 1 hour to reduce database load.
    """
    model = Service
    template_name = 'services/client_catalog.html'
    context_object_name = 'services'
    paginate_by = 12

    def get_queryset(self):
        cache_key = 'client_service_catalog_services'
        services = cache.get(cache_key)
        if services is None:
            services = list(Service.objects.filter(is_active=True).select_related('category'))
            cache.set(cache_key, services, 3600)
        return services

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Cache packages as well
        packages_cache_key = 'client_service_catalog_packages'
        packages = cache.get(packages_cache_key)
        if packages is None:
            packages = ServicePackage.objects.filter(is_active=True).prefetch_related('services')
            cache.set(packages_cache_key, packages, 3600)
        ctx['packages'] = packages
        return ctx


class RequestServiceQuoteView(LoginRequiredMixin, View):
    """Client requests a quotation for a single service."""
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

        note_json = json.dumps({"html": f"<p>Auto-generated from client request for service: {service.name}</p>", "delta": ""})

        quotation = QuotationService.create_quotation(
            client=client_org,
            items_data=items_data,
            issue_date=today,
            valid_until=valid_until,
            notes=note_json,
            created_by=request.user
        )

        messages.success(request, f"Quotation {quotation.quotation_number} created.")
        return redirect('client_quotation_detail', pk=quotation.pk)


class RequestPackageQuoteView(LoginRequiredMixin, View):
    """Client requests a quotation for an entire service package."""
    def get(self, request, package_pk):
        package = get_object_or_404(ServicePackage, pk=package_pk, is_active=True)
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
        } for service in package.services.all()]

        note_json = json.dumps({
            "html": f"<p>Quotation for package: {package.name}</p>"
                    f"<p>Includes: {', '.join([s.name for s in package.services.all()])}</p>",
            "delta": ""
        })

        quotation = QuotationService.create_quotation(
            client=client_org,
            items_data=items_data,
            issue_date=today,
            valid_until=valid_until,
            notes=note_json,
            created_by=request.user
        )

        messages.success(request, f"Quotation for package '{package.name}' created (ref. {quotation.quotation_number}).")
        return redirect('client_quotation_detail', pk=quotation.pk)