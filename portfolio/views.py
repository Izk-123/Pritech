"""
Portfolio App Views
===================
Handles the public-facing website including:
- Homepage with services, projects, inquiry form, newsletter signup.
- Newsletter confirmation and unsubscribe (GDPR compliant).
- GDPR data export and deletion requests.
- Rate limiting and honeypot anti-spam.
- Admin email notifications for new inquiries.
- Caching for performance.
"""

import json
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView, FormView, View

from accounts.decorators import get_client_ip, rate_limit
from services.models import Service, ServiceCategory
from .forms import InquiryForm, NewsletterForm
from .models import (
    PortfolioProject,
    PortfolioSettings,
    NewsletterSubscriber,
    Inquiry,
)


# -----------------------------------------------------------------------------
# Homepage with integrated inquiry form
# -----------------------------------------------------------------------------

@method_decorator(
    rate_limit(key_func=get_client_ip, rate="5/h", method="POST", block=True),
    name="dispatch",
)
class HomeView(TemplateView, FormView):
    """
    Displays the homepage with services, projects, and a contact form.
    Handles inquiry form submission with honeypot and rate limiting.
    Sends email notification to admin on successful inquiry.
    Uses caching for database-heavy queries.
    """
    template_name = "portfolio/home.html"
    form_class = InquiryForm
    success_url = "/"  # stay on same page

    def get_context_data(self, **kwargs):
        """Inject all required context for the homepage."""
        context = super().get_context_data(**kwargs)

        # Singleton settings – no caching needed (single row)
        context["portfolio_settings"] = PortfolioSettings.get()

        # Cache featured projects (1 hour)
        context["projects"] = cache.get_or_set(
            "featured_projects",
            lambda: list(PortfolioProject.objects.filter(is_featured=True)[:6]),
            3600,
        )

        # Cache active services (1 hour)
        context["services"] = cache.get_or_set(
            "active_services",
            lambda: list(
                Service.objects.filter(is_active=True)
                .select_related("category")[:9]
            ),
            3600,
        )

        # Cache service categories (1 hour)
        context["categories"] = cache.get_or_set(
            "service_categories",
            lambda: list(ServiceCategory.objects.prefetch_related("services")),
            3600,
        )

        # Add forms
        context["inquiry_form"] = self.get_form()
        context["newsletter_form"] = NewsletterForm()

        return context

    def form_valid(self, form):
        """Handle valid inquiry form submission."""
        inquiry = form.save()

        # Send admin email notification
        send_mail(
            subject=f"[Pritech Inquiry] {inquiry.subject}",
            message=(
                f"Name: {inquiry.name}\n"
                f"Email: {inquiry.email}\n"
                f"Phone: {inquiry.phone or 'Not provided'}\n\n"
                f"Message:\n{inquiry.message}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_EMAIL],
            fail_silently=True,  # Don't break the user experience if email fails
        )

        messages.success(self.request, "Thank you! We will be in touch shortly.")
        return super().form_valid(form)

    def form_invalid(self, form):
        """Show errors on the same page."""
        messages.error(
            self.request,
            "Please correct the errors below."
        )
        return self.render_to_response(self.get_context_data(form=form))


# -----------------------------------------------------------------------------
# Newsletter subscription with double opt-in (GDPR compliant)
# -----------------------------------------------------------------------------

@rate_limit(key_func=get_client_ip, rate="10/h", method="POST", block=True)
def newsletter_subscribe(request):
    """
    Subscribe a new email address. Sends a confirmation email with a unique token.
    Rate limited to 10 requests per hour per IP.
    """
    if request.method != "POST":
        return redirect("home")

    form = NewsletterForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Invalid email address or consent not given.")
        return redirect("home")

    email = form.cleaned_data["email"]
    consent = form.cleaned_data["consent"]
    ip = get_client_ip(request)

    # Get or create subscriber (allow reactivation of unsubscribed users)
    subscriber, created = NewsletterSubscriber.objects.get_or_create(
        email=email,
        defaults={
            "ip_address": ip,
            "consent_given": consent,
            "consent_ip": ip,
        },
    )

    if not created and subscriber.unsubscribed_at is not None:
        # Reactivate – reset unsubscribed and regenerate token
        subscriber.unsubscribed_at = None
        subscriber.is_confirmed = False
        subscriber.confirmation_token = uuid.uuid4()
        subscriber.save()
        created = True  # treat as new for resending

    if created or not subscriber.is_confirmed:
        # Send confirmation email
        confirm_url = request.build_absolute_uri(
            reverse("newsletter_confirm", args=[subscriber.confirmation_token])
        )
        send_mail(
            subject="Confirm your subscription to Pritech Newsletter",
            message=(
                f"Please click the link below to confirm your subscription:\n\n"
                f"{confirm_url}\n\n"
                f"This link expires in 7 days."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        messages.success(
            request,
            "Please check your email to confirm your subscription."
        )
    else:
        messages.info(request, "You are already subscribed.")

    return redirect("home")


def newsletter_confirm(request, token):
    """
    Confirm a newsletter subscription using the unique token.
    Marks the subscriber as confirmed and stores confirmation timestamp.
    Sends a notification email to admin.
    """
    subscriber = get_object_or_404(NewsletterSubscriber, confirmation_token=token)

    if not subscriber.is_confirmed:
        subscriber.is_confirmed = True
        subscriber.confirmed_at = timezone.now()
        subscriber.save()

        # Notify admin of new confirmed subscriber
        send_mail(
            subject=f"New newsletter subscriber: {subscriber.email}",
            message=(
                f"Email: {subscriber.email}\n"
                f"IP: {subscriber.consent_ip}\n"
                f"Subscribed at: {subscriber.subscribed_at}\n"
                f"Confirmed at: {subscriber.confirmed_at}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_EMAIL],
            fail_silently=True,
        )
        messages.success(request, "Subscription confirmed. Thank you!")
    else:
        messages.info(request, "Already confirmed.")

    return redirect("home")


def newsletter_unsubscribe(request, token):
    """
    Unsubscribe a user – soft delete (set unsubscribed_at timestamp).
    """
    subscriber = get_object_or_404(NewsletterSubscriber, confirmation_token=token)
    if not subscriber.unsubscribed_at:
        subscriber.unsubscribed_at = timezone.now()
        subscriber.save()
        messages.success(request, "You have been unsubscribed.")
    else:
        messages.info(request, "Already unsubscribed.")
    return redirect("home")


# -----------------------------------------------------------------------------
# GDPR compliance endpoints
# -----------------------------------------------------------------------------

@require_http_methods(["POST"])
def gdpr_data_export(request):
    """
    Export all stored data for a given email in JSON format.
    The user must provide the email address (no authentication required
    because subscribers don't have accounts). We send the export to the email.
    For simplicity, we generate a downloadable JSON file directly.
    """
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
    response = HttpResponse(
        json.dumps(data, indent=2), content_type="application/json"
    )
    response["Content-Disposition"] = f'attachment; filename="pritech_data_{subscriber.email}.json"'
    return response


@require_http_methods(["POST"])
def gdpr_data_deletion(request):
    """
    Permanently delete a subscriber's data (right to be forgotten).
    """
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