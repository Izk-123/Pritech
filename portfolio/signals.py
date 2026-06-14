"""
Portfolio App Signals
=====================
Clear cached data when relevant models change.
Also clears cache when the many-to-many relation between Project and Service changes.
"""

from django.core.cache import cache
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from .models import PortfolioProject
from services.models import Service, ServiceCategory


@receiver([post_save, post_delete], sender=PortfolioProject)
@receiver([post_save, post_delete], sender=Service)
@receiver([post_save, post_delete], sender=ServiceCategory)
@receiver(m2m_changed, sender=PortfolioProject.services.through)
def clear_portfolio_cache(sender, **kwargs):
    """
    Clear the cached values used in HomeView when any of the relevant models change,
    including when services are added/removed from a project.
    """
    cache.delete_many([
        "featured_projects",
        "active_services",
        "service_categories",
    ])