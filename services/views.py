# services/views.py
"""
Services App Views
------------------
Handles:
- Staff CRUD for services, categories, packages (with role‑based access)
- Client service catalog (with caching)
- Client service requests (new workflow)
- Staff service request management (approve/reject/assign)
- Quotation generation for services and packages (with rate limiting)
- Service analytics (staff only)
- HTMX inline status toggle for services
"""

import csv
import json
from decimal import Decimal
from datetime import date, timedelta

from django.core.cache import cache
from django.core.paginator import Paginator
from django.http import HttpResponse, Http404
from django.db.models import Q, Count, Sum
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.db import transaction

from core.mixins import RoleRequiredMixin
from accounts.decorators import rate_limit, get_client_ip
from .models import Service, ServiceCategory, ServicePackage, ServiceRequest, ClientService, ServiceAssignment
from .forms import ServiceForm, ServiceCategoryForm, ServicePackageForm, ServiceRequestForm
from finance.services import QuotationService
from finance.models import Quotation, QuotationItem


# -----------------------------------------------------------------------------
# Helper function for HTMX status toggle
# -----------------------------------------------------------------------------
def service_toggle_status(request, pk):
    """
    HTMX endpoint: toggle the is_active status of a service.
    Returns the new status badge HTML.
    """
    if not request.user.is_authenticated or not (request.user.is_staff or request.user.has_perm('services.change_service')):
        return HttpResponse(status=403)
    service = get_object_or_404(Service, pk=pk)
    service.is_active = not service.is_active
    service.save()
    badge_class = 'bg-success' if service.is_active else 'bg-secondary'
    status_text = 'Active' if service.is_active else 'Inactive'
    html = f'<span class="badge {badge_class} status-badge" style="cursor:pointer;">{status_text} <i class="bi bi-arrow-repeat ms-1"></i></span>'
    return HttpResponse(html)


# -----------------------------------------------------------------------------
# STAFF: Service Management
# -----------------------------------------------------------------------------

class ServiceListView(RoleRequiredMixin, ListView):
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
        status_filter = self.request.GET.get('status')
        if status_filter == 'active':
            qs = qs.filter(is_active=True)
        elif status_filter == 'inactive':
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['current_status'] = self.request.GET.get('status', '')
        return ctx


class ServiceDetailView(RoleRequiredMixin, DetailView):
    model = Service
    template_name = 'services/detail.html'
    context_object_name = 'service'
    required_roles = ['ADMIN', 'SALES', 'FINANCE']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Calculate total invoiced amount for this service (optional)
        from finance.models import InvoiceItem
        total = InvoiceItem.objects.filter(
            description=self.object.name,
            invoice__status='paid'
        ).aggregate(total=Sum('total'))['total'] or 0
        ctx['total_invoiced'] = total
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
# STAFF: Categories (restricted to ADMIN/SALES)
# -----------------------------------------------------------------------------

class ServiceCategoryListView(RoleRequiredMixin, ListView):
    model = ServiceCategory
    template_name = 'services/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20
    required_roles = ['ADMIN', 'SALES']


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
# STAFF: Packages (restricted to ADMIN/SALES)
# -----------------------------------------------------------------------------

class ServicePackageListView(RoleRequiredMixin, ListView):
    model = ServicePackage
    template_name = 'services/package_list.html'
    context_object_name = 'packages'
    paginate_by = 20
    required_roles = ['ADMIN', 'SALES']

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
        # Prevent deletion if referenced by any Plan (foreign key added to finance.Plan)
        from finance.models import Plan
        if Plan.objects.filter(service_package=package).exists():
            messages.error(
                request,
                f"Cannot delete package '{package.name}' because it is linked to an active plan."
            )
            return redirect('service_package_list')
        return super().delete(request, *args, **kwargs)


# -----------------------------------------------------------------------------
# CLIENT: Service Catalog (with caching, rate‑limited quote requests)
# -----------------------------------------------------------------------------

class ClientServiceCatalogView(LoginRequiredMixin, ListView):
    model = Service
    template_name = 'services/client_catalog.html'
    context_object_name = 'services'
    paginate_by = 12

    def get_queryset(self):
        cache_key = 'client_service_catalog_service_ids'
        service_ids = cache.get(cache_key)
        if service_ids is None:
            service_ids = list(Service.objects.filter(is_active=True).values_list('id', flat=True))
            cache.set(cache_key, service_ids, 3600)
        return Service.objects.filter(id__in=service_ids).select_related('category')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        packages_cache_key = 'client_service_catalog_packages'
        packages = cache.get(packages_cache_key)
        if packages is None:
            packages = ServicePackage.objects.filter(is_active=True).prefetch_related('services')
            cache.set(packages_cache_key, packages, 3600)
        ctx['packages'] = packages
        return ctx


@method_decorator(rate_limit(key_func=get_client_ip, rate='5/h', method='GET', block=True), name='dispatch')
class RequestServiceQuoteView(LoginRequiredMixin, View):
    def get(self, request, service_pk):
        service = get_object_or_404(Service, pk=service_pk, is_active=True)
        client_org = request.user.client_organization
        if not client_org:
            messages.error(request, "Your account is not linked to a client organization.")
            return redirect('client_service_catalog')

        today = timezone.now().date()
        valid_until = today + timedelta(days=30)

        items_data = [{
            'description': service.name,
            'quantity': Decimal('1'),
            'unit_price': service.base_price,
        }]
        if service.billing_type == 'recurring':
            items_data[0]['description'] += f" (recurring {service.unit})"

        note_json = json.dumps({
            "html": f"<p>Auto-generated from client request for service: {service.name}</p>",
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
        messages.success(request, f"Quotation {quotation.quotation_number} created.")
        return redirect('client_quotation_detail', pk=quotation.pk)


@method_decorator(rate_limit(key_func=get_client_ip, rate='5/h', method='GET', block=True), name='dispatch')
class RequestPackageQuoteView(LoginRequiredMixin, View):
    def get(self, request, package_pk):
        package = get_object_or_404(ServicePackage, pk=package_pk, is_active=True)
        client_org = request.user.client_organization
        if not client_org:
            messages.error(request, "Your account is not linked to a client organization.")
            return redirect('client_service_catalog')

        today = timezone.now().date()
        valid_until = today + timedelta(days=30)

        items_data = [{
            'description': f"Package: {package.name} (monthly subscription)",
            'quantity': Decimal('1'),
            'unit_price': package.monthly_price,
        }]

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
        messages.success(request, f"Quotation for package '{package.name}' created.")
        return redirect('client_quotation_detail', pk=quotation.pk)


# -----------------------------------------------------------------------------
# Service Request Workflow (Client & Staff)
# -----------------------------------------------------------------------------

class CreateServiceRequestView(LoginRequiredMixin, CreateView):
    model = ServiceRequest
    form_class = ServiceRequestForm
    template_name = 'services/service_request_form.html'
    success_url = reverse_lazy('client_service_requests')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.client_organization:
            messages.error(request, "Your account is not linked to a client organization.")
            return redirect('client_service_catalog')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.client = self.request.user.client_organization
        form.instance.status = 'pending'
        messages.success(self.request, "Your service request has been submitted. We will review it shortly.")
        return super().form_valid(form)


class ClientServiceRequestListView(LoginRequiredMixin, ListView):
    model = ServiceRequest
    template_name = 'services/client_service_request_list.html'
    context_object_name = 'requests'
    paginate_by = 20

    def get_queryset(self):
        client_org = self.request.user.client_organization
        if not client_org:
            return ServiceRequest.objects.none()
        return ServiceRequest.objects.filter(client=client_org).order_by('-requested_at')


class StaffServiceRequestListView(RoleRequiredMixin, ListView):
    model = ServiceRequest
    template_name = 'services/staff_service_request_list.html'
    context_object_name = 'requests'
    paginate_by = 20
    required_roles = ['ADMIN', 'SALES', 'TECHNICIAN']

    def get_queryset(self):
        qs = ServiceRequest.objects.select_related('client', 'service')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = ServiceRequest.STATUS_CHOICES
        ctx['current_status'] = self.request.GET.get('status', '')
        from accounts.models import User
        ctx['all_technicians'] = User.objects.filter(user_type='staff', is_active=True)
        return ctx


class ApproveServiceRequestView(RoleRequiredMixin, View):
    required_roles = ['ADMIN', 'SALES']

    def post(self, request, pk):
        service_request = get_object_or_404(ServiceRequest, pk=pk, status='pending')
        with transaction.atomic():
            service_request.status = 'approved'
            service_request.reviewed_by = request.user
            service_request.reviewed_at = timezone.now()
            service_request.save()

            today = date.today()
            valid_until = today + timedelta(days=30)
            items_data = [{
                'description': service_request.service.name,
                'quantity': Decimal('1'),
                'unit_price': service_request.service.base_price,
            }]
            note_json = json.dumps({
                "html": f"<p>Service request #{service_request.id} approved.</p>",
                "delta": ""
            })
            quotation = QuotationService.create_quotation(
                client=service_request.client,
                items_data=items_data,
                issue_date=today,
                valid_until=valid_until,
                notes=note_json,
                created_by=request.user
            )
            service_request.quotation = quotation
            service_request.status = 'quoted'
            service_request.save(update_fields=['quotation', 'status'])

        messages.success(request, f"Service request approved. Quotation {quotation.quotation_number} created.")
        return redirect('staff_service_request_list')


class RejectServiceRequestView(RoleRequiredMixin, View):
    required_roles = ['ADMIN', 'SALES']

    def post(self, request, pk):
        service_request = get_object_or_404(ServiceRequest, pk=pk, status='pending')
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, "Please provide a rejection reason.")
            return redirect('staff_service_request_list')

        service_request.status = 'rejected'
        service_request.rejection_reason = reason
        service_request.reviewed_by = request.user
        service_request.reviewed_at = timezone.now()
        service_request.save()
        messages.warning(request, f"Service request rejected: {reason}")
        return redirect('staff_service_request_list')


class AssignTechnicianView(RoleRequiredMixin, View):
    required_roles = ['ADMIN', 'SALES']

    def post(self, request, pk):
        service_request = get_object_or_404(ServiceRequest, pk=pk, status__in=['quoted', 'approved'])
        tech_id = request.POST.get('technician_id')
        if not tech_id:
            messages.error(request, "Please select a technician.")
            return redirect('staff_service_request_list')

        from accounts.models import User
        technician = get_object_or_404(User, pk=tech_id, user_type='staff')
        assignment = ServiceAssignment.objects.create(
            service_request=service_request,
            technician=technician
        )
        service_request.status = 'in_progress'
        service_request.save(update_fields=['status'])
        messages.success(request, f"Assigned to {technician.get_full_name() or technician.email}")
        return redirect('staff_service_request_list')


class TechnicianAssignmentListView(RoleRequiredMixin, ListView):
    model = ServiceAssignment
    template_name = 'services/technician_assignments.html'
    context_object_name = 'assignments'
    required_roles = ['TECHNICIAN', 'ADMIN']

    def get_queryset(self):
        return ServiceAssignment.objects.filter(
            technician=self.request.user,
            completed_at__isnull=True
        ).select_related('service_request', 'service_request__client', 'service_request__service')


class CompleteAssignmentView(RoleRequiredMixin, View):
    required_roles = ['TECHNICIAN', 'ADMIN']

    def post(self, request, pk):
        assignment = get_object_or_404(ServiceAssignment, pk=pk, technician=request.user, completed_at__isnull=True)
        assignment.completed_at = timezone.now()
        assignment.save()
        assignment.service_request.status = 'completed'
        assignment.service_request.save(update_fields=['status'])
        messages.success(request, "Service marked as completed.")
        return redirect('technician_assignments')


# -----------------------------------------------------------------------------
# Service Analytics (Staff only)
# -----------------------------------------------------------------------------

class ServiceAnalyticsView(RoleRequiredMixin, TemplateView):
    template_name = 'services/service_analytics.html'
    required_roles = ['ADMIN', 'FINANCE']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        from finance.models import InvoiceItem
        revenue_by_service = InvoiceItem.objects.filter(
            invoice__status='paid',
            description__in=Service.objects.values_list('name', flat=True)
        ).values('description').annotate(total=Sum('total')).order_by('-total')[:10]

        most_requested = ServiceRequest.objects.filter(
            status__in=['approved', 'completed', 'quoted']
        ).values('service__name').annotate(count=Count('id')).order_by('-count')[:10]

        tech_performance = ServiceAssignment.objects.filter(
            completed_at__isnull=False
        ).values('technician__email', 'technician__first_name', 'technician__last_name')\
         .annotate(completed_count=Count('id')).order_by('-completed_count')[:10]

        ctx['revenue_by_service'] = revenue_by_service
        ctx['most_requested_services'] = most_requested
        ctx['technician_performance'] = tech_performance
        return ctx