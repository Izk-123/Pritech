"""
Portfolio App URL Configuration
===============================
Includes public homepage, portfolio pages, newsletter flows, and GDPR endpoints.
"""

from django.urls import path
from .views import (
    HomeView,
    PortfolioListView,
    PortfolioDetailView,
    CategoryProjectsView,
    newsletter_subscribe,
    newsletter_confirm,
    newsletter_unsubscribe,
    gdpr_data_export,
    gdpr_data_deletion,
    PrivacyPolicyView,
)


urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("portfolio/", PortfolioListView.as_view(), name="portfolio_list"),
    path("portfolio/category/<slug:slug>/", CategoryProjectsView.as_view(), name="category_projects"),
    path("portfolio/project/<slug:slug>/", PortfolioDetailView.as_view(), name="project_detail"),
    path("newsletter/subscribe/", newsletter_subscribe, name="newsletter_subscribe"),
    path("newsletter/confirm/<uuid:token>/", newsletter_confirm, name="newsletter_confirm"),
    path("newsletter/unsubscribe/<uuid:token>/", newsletter_unsubscribe, name="newsletter_unsubscribe"),
    path("gdpr/export/", gdpr_data_export, name="gdpr_export"),
    path("gdpr/delete/", gdpr_data_deletion, name="gdpr_delete"),
    path("privacy-policy/", PrivacyPolicyView.as_view(), name="privacy_policy"),
]