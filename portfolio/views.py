"""
Portfolio App Views
===================
Handles public portfolio pages:
- Homepage (integrated with services, projects, inquiry)
- Portfolio listing (with filters by category, technology, search)
- Project detail (with gallery, testimonials, related projects)
- Category view
- Also includes newsletter, GDPR, etc.
"""

import json
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Q, Count, Prefetch   # <-- added Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, DetailView, TemplateView, FormView

from accounts.decorators import get_client_ip, rate_limit
from services.models import Service, ServiceCategory
from .forms import InquiryForm, NewsletterForm
from .models import (
    PortfolioProject, PortfolioCategory, PortfolioTechnology,
    PortfolioSettings, Inquiry, NewsletterSubscriber, Testimonial   # <-- added Testimonial
)


# -----------------------------------------------------------------------------
# Homepage (with inquiry form)
# -----------------------------------------------------------------------------
@method_decorator(
    rate_limit(key_func=get_client_ip, rate="5/h", method="POST", block=True),
    name="dispatch",
)
class HomeView(TemplateView, FormView):
    template_name = "portfolio/home.html"
    form_class = InquiryForm
    success_url = "/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["portfolio_settings"] = PortfolioSettings.get()
        context["projects"] = cache.get_or_set(
            "featured_projects",
            lambda: list(PortfolioProject.objects.filter(status="published", is_featured=True)[:6]),
            3600,
        )
        context["services"] = cache.get_or_set(
            "active_services",
            lambda: list(Service.objects.filter(is_active=True).select_related("category")[:9]),
            3600,
        )
        context["categories"] = cache.get_or_set(
            "service_categories",
            lambda: list(ServiceCategory.objects.prefetch_related("services")),
            3600,
        )
        context["inquiry_form"] = self.get_form()
        context["newsletter_form"] = NewsletterForm()
        return context

    def form_valid(self, form):
        inquiry = form.save()
        send_mail(
            subject=f"[Pritech Inquiry] {inquiry.subject}",
            message=f"Name: {inquiry.name}\nEmail: {inquiry.email}\nPhone: {inquiry.phone}\n\nMessage:\n{inquiry.message}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_EMAIL],
            fail_silently=True,
        )
        messages.success(self.request, "Thank you! We will be in touch shortly.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return self.render_to_response(self.get_context_data(form=form))


# -----------------------------------------------------------------------------
# Portfolio Listing (with filters)
# -----------------------------------------------------------------------------
class PortfolioListView(ListView):
    model = PortfolioProject
    template_name = "portfolio/portfolio_list.html"
    context_object_name = "projects"
    paginate_by = 12

    def get_queryset(self):
        qs = PortfolioProject.objects.filter(status="published").select_related("category").prefetch_related("technologies")
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(client_name__icontains=q) | Q(description__icontains=q))
        category_slug = self.request.GET.get("category")
        if category_slug:
            qs = qs.filter(category__slug=category_slug)
        tech_id = self.request.GET.get("tech")
        if tech_id:
            qs = qs.filter(technologies__id=tech_id)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = PortfolioCategory.objects.filter(is_active=True)
        ctx["technologies"] = PortfolioTechnology.objects.filter(is_active=True)
        ctx["current_category"] = self.request.GET.get("category", "")
        ctx["current_tech"] = self.request.GET.get("tech", "")
        ctx["search_query"] = self.request.GET.get("q", "")
        return ctx


# -----------------------------------------------------------------------------
# Portfolio Detail (fixed: only approved testimonials)
# -----------------------------------------------------------------------------
class PortfolioDetailView(DetailView):
    model = PortfolioProject
    template_name = "portfolio/portfolio_detail.html"
    context_object_name = "project"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        # Prefetch only approved testimonials
        return PortfolioProject.objects.filter(status="published").select_related("category").prefetch_related(
            "technologies",
            "services",
            "images",
            Prefetch("testimonials", queryset=Testimonial.objects.filter(is_approved=True))
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Related projects
        related = PortfolioProject.objects.filter(
            status="published",
            category=self.object.category
        ).exclude(pk=self.object.pk)[:4]
        ctx["related_projects"] = related

        # Optional tracking – safely handle missing or different field names
        try:
            from tracking.models import PageVisit
            # Attempt to create a visit record using the correct field names
            # Common field names: 'url', 'page_url', 'path', 'ip', 'ip_address'
            # We'll try a flexible approach
            visit_kwargs = {}
            # Try to match the model's fields dynamically
            if hasattr(PageVisit, 'path'):
                visit_kwargs['path'] = self.request.path
            elif hasattr(PageVisit, 'page_url'):
                visit_kwargs['page_url'] = self.request.path
            elif hasattr(PageVisit, 'url'):
                visit_kwargs['url'] = self.request.path

            if hasattr(PageVisit, 'ip_address'):
                visit_kwargs['ip_address'] = self.request.META.get('REMOTE_ADDR')
            elif hasattr(PageVisit, 'ip'):
                visit_kwargs['ip'] = self.request.META.get('REMOTE_ADDR')
            elif hasattr(PageVisit, 'visitor_ip'):
                visit_kwargs['visitor_ip'] = self.request.META.get('REMOTE_ADDR')

            if hasattr(PageVisit, 'user_agent'):
                visit_kwargs['user_agent'] = self.request.META.get('HTTP_USER_AGENT', '')[:200]

            if visit_kwargs:
                PageVisit.objects.create(**visit_kwargs)
        except Exception as e:
            # Silently fail – don't break the page if tracking fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to record page visit: {e}")

        return ctx


# -----------------------------------------------------------------------------
# Category Projects
# -----------------------------------------------------------------------------
class CategoryProjectsView(ListView):
    model = PortfolioProject
    template_name = "portfolio/category_projects.html"
    context_object_name = "projects"
    paginate_by = 12

    def get_queryset(self):
        self.category = get_object_or_404(PortfolioCategory, slug=self.kwargs["slug"], is_active=True)
        return PortfolioProject.objects.filter(status="published", category=self.category).select_related("category")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["category"] = self.category
        return ctx


# -----------------------------------------------------------------------------
# Newsletter subscription (GDPR compliant)
# -----------------------------------------------------------------------------
@rate_limit(key_func=get_client_ip, rate="10/h", method="POST", block=True)
def newsletter_subscribe(request):
    if request.method != "POST":
        return redirect("home")

    form = NewsletterForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Invalid email address or consent not given.")
        return redirect("home")

    email = form.cleaned_data["email"]
    consent = form.cleaned_data["consent"]
    ip = get_client_ip(request)

    subscriber, created = NewsletterSubscriber.objects.get_or_create(
        email=email,
        defaults={
            "ip_address": ip,
            "consent_given": consent,
            "consent_ip": ip,
        },
    )

    if not created and subscriber.unsubscribed_at is not None:
        subscriber.unsubscribed_at = None
        subscriber.is_confirmed = False
        subscriber.confirmation_token = uuid.uuid4()
        subscriber.save()
        created = True

    if created or not subscriber.is_confirmed:
        confirm_url = request.build_absolute_uri(
            reverse("newsletter_confirm", args=[subscriber.confirmation_token])
        )
        send_mail(
            subject="Confirm your subscription to Pritech Newsletter",
            message=f"Please click the link below to confirm your subscription:\n\n{confirm_url}\n\nThis link expires in 7 days.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        messages.success(request, "Please check your email to confirm your subscription.")
    else:
        messages.info(request, "You are already subscribed.")

    return redirect("home")


def newsletter_confirm(request, token):
    subscriber = get_object_or_404(NewsletterSubscriber, confirmation_token=token)

    if not subscriber.is_confirmed:
        subscriber.is_confirmed = True
        subscriber.confirmed_at = timezone.now()
        subscriber.save()
        send_mail(
            subject=f"New newsletter subscriber: {subscriber.email}",
            message=f"Email: {subscriber.email}\nIP: {subscriber.consent_ip}\nSubscribed at: {subscriber.subscribed_at}\nConfirmed at: {subscriber.confirmed_at}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_EMAIL],
            fail_silently=True,
        )
        messages.success(request, "Subscription confirmed. Thank you!")
    else:
        messages.info(request, "Already confirmed.")

    return redirect("home")


def newsletter_unsubscribe(request, token):
    subscriber = get_object_or_404(NewsletterSubscriber, confirmation_token=token)
    if not subscriber.unsubscribed_at:
        subscriber.unsubscribed_at = timezone.now()
        subscriber.save()
        messages.success(request, "You have been unsubscribed.")
    else:
        messages.info(request, "Already unsubscribed.")
    return redirect("home")


# -----------------------------------------------------------------------------
# GDPR endpoints
# -----------------------------------------------------------------------------
@require_http_methods(["POST"])
def gdpr_data_export(request):
    email = request.POST.get("email")
    if not email:
        messages.error(request, "Email address required.")
        return redirect("home")

    try:
        subscriber = NewsletterSubscriber.objects.get(email=email)
    except NewsletterSubscriber.DoesNotExist:
        messages.error(request, "No subscriber found with that email.")
        return redirect("home")

    data = {
        "email": subscriber.email,
        "subscribed_at": subscriber.subscribed_at.isoformat(),
        "confirmed_at": subscriber.confirmed_at.isoformat() if subscriber.confirmed_at else None,
        "ip_address": subscriber.ip_address,
        "consent_given": subscriber.consent_given,
        "consent_ip": subscriber.consent_ip,
        "unsubscribed_at": subscriber.unsubscribed_at.isoformat() if subscriber.unsubscribed_at else None,
    }
    response = HttpResponse(json.dumps(data, indent=2), content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="pritech_data_{subscriber.email}.json"'
    return response


@require_http_methods(["POST"])
def gdpr_data_deletion(request):
    email = request.POST.get("email")
    if not email:
        messages.error(request, "Email address required.")
        return redirect("home")

    try:
        subscriber = NewsletterSubscriber.objects.get(email=email)
        subscriber.delete()
        messages.success(request, "Your data has been permanently deleted.")
    except NewsletterSubscriber.DoesNotExist:
        messages.error(request, "No subscriber found with that email.")
    return redirect("home")


class PrivacyPolicyView(TemplateView):
    template_name = "portfolio/privacy_policy.html"