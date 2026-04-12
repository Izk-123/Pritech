from django.views.generic import TemplateView, CreateView
from django.urls import reverse_lazy
from django.contrib import messages
from .models import PortfolioProject, Inquiry
from .forms import InquiryForm
from services.models import Service, ServiceCategory


class HomeView(TemplateView):
    template_name = 'portfolio/home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['projects'] = PortfolioProject.objects.filter(is_featured=True)[:6]
        ctx['categories'] = ServiceCategory.objects.prefetch_related('services')
        ctx['inquiry_form'] = InquiryForm()
        return ctx


class InquiryCreateView(CreateView):
    model = Inquiry
    form_class = InquiryForm
    template_name = 'portfolio/home.html'
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        form.save()
        messages.success(self.request, 'Thank you! We will be in touch shortly.')
        return super().form_valid(form)
