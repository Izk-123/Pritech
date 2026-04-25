from django.views.generic import TemplateView, CreateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import NewsletterSubscriber, PortfolioProject, Inquiry
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


@require_POST
def newsletter_subscribe(request):
    email = request.POST.get('email', '').strip().lower()
    if email:
        subscriber, created = NewsletterSubscriber.objects.get_or_create(email=email)
        if created:
            messages.success(request, 'You have been subscribed to our newsletter.')
        else:
            messages.info(request, 'You are already subscribed.')
    else:
        messages.error(request, 'Please provide a valid email address.')

    # Redirect back to the previous page (or home)
    return redirect(request.META.get('HTTP_REFERER', 'home'))