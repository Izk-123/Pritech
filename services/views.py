from django.views.generic import ListView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import Service, ServiceCategory
from .forms import ServiceForm


class ServiceListView(LoginRequiredMixin, ListView):
    model = Service
    template_name = 'services/list.html'
    context_object_name = 'services'

    def get_queryset(self):
        return Service.objects.select_related('category').filter(is_active=True)


class ServiceCreateView(LoginRequiredMixin, CreateView):
    model = Service
    form_class = ServiceForm
    template_name = 'services/form.html'
    success_url = reverse_lazy('service_list')


class ServiceUpdateView(LoginRequiredMixin, UpdateView):
    model = Service
    form_class = ServiceForm
    template_name = 'services/form.html'
    success_url = reverse_lazy('service_list')
