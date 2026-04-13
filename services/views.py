from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from core.mixins import RoleRequiredMixin
from .models import Service, ServiceCategory, ServicePackage
from .forms import ServiceForm, ServiceCategoryForm, ServicePackageForm


# ---------- Service Views ----------
class ServiceListView(LoginRequiredMixin, ListView):
    model = Service
    template_name = 'services/list.html'          # ✅ matches existing template
    context_object_name = 'services'

    def get_queryset(self):
        return Service.objects.select_related('category').filter(is_active=True)


class ServiceCreateView(RoleRequiredMixin, CreateView):
    model = Service
    form_class = ServiceForm
    template_name = 'services/form.html'          # ✅ matches existing template
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