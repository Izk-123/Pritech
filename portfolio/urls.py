"""
Portfolio App URL Configuration
===============================
Includes public homepage, inquiry form, newsletter flows, and GDPR endpoints.
"""

from django.urls import path
from .views import (
    HomeView,
    PrivacyPolicyView,
    newsletter_subscribe,
    newsletter_confirm,
    newsletter_unsubscribe,
    gdpr_data_export,
    gdpr_data_deletion,
)

urlpatterns = [
    # Main homepage (handles GET and POST for inquiry)
    path("", HomeView.as_view(), name="home"),

    # Newsletter flows
    path("newsletter/subscribe/", newsletter_subscribe, name="newsletter_subscribe"),
    path("newsletter/confirm/<uuid:token>/", newsletter_confirm, name="newsletter_confirm"),
    path("newsletter/unsubscribe/<uuid:token>/", newsletter_unsubscribe, name="newsletter_unsubscribe"),

    # GDPR compliance
    path("gdpr/export/", gdpr_data_export, name="gdpr_export"),
    path("gdpr/delete/", gdpr_data_deletion, name="gdpr_delete"),
    
    path("privacy-policy/", PrivacyPolicyView.as_view(), name="privacy_policy"),
]