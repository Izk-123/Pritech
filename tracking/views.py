"""
Tracking App Views
==================
- Consent opt-out page.
- GDPR data export and deletion for authenticated users.
- Basic analytics dashboard for staff.
"""

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse, JsonResponse
from django.core.cache import cache
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
import json

from .models import TrackingConsent, PageVisit, UserActivity
from accounts.decorators import get_client_ip


def tracking_opt_out(request):
    """
    Allow users (authenticated or anonymous) to withdraw consent for tracking.
    Stores a `consent_given=False` record and clears cache.
    """
    if request.method == "POST":
        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key

        consent_obj = None
        if user:
            consent_obj = TrackingConsent.objects.filter(user=user).first()
        elif session_key:
            consent_obj = TrackingConsent.objects.filter(session_key=session_key).first()

        if consent_obj:
            consent_obj.consent_given = False
            consent_obj.withdrawn_at = timezone.now()
            consent_obj.save()
        else:
            # Create a new record with withdrawal
            TrackingConsent.objects.create(
                user=user,
                session_key=session_key,
                consent_given=False,
                withdrawn_at=timezone.now(),
                consent_ip=get_client_ip(request),
            )

        # Clear cache
        cache_key = f"tracking_consent_{user.id if user else session_key}"
        cache.delete(cache_key)

        messages.success(request, "You have opted out of tracking. No further visits will be logged.")
        return redirect("home")

    return render(request, "tracking/opt_out.html")


@login_required
def tracking_data_export(request):
    """
    GDPR Right to Access: export all of the user's own tracking data as JSON.
    """
    user = request.user
    visits = PageVisit.objects.filter(user=user).values(
        "page_url", "timestamp", "user_agent", "consent_given", "ip_hash"
    )
    activities = UserActivity.objects.filter(user=user).values(
        "action", "timestamp", "user_agent", "ip_hash"
    )
    data = {
        "page_visits": list(visits),
        "user_activities": list(activities),
    }
    response = HttpResponse(json.dumps(data, indent=2, default=str), content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="tracking_data_{user.email}.json"'
    return response


@login_required
@require_http_methods(["POST"])
def tracking_data_delete(request):
    """
    GDPR Right to Erasure: delete all of the user's own tracking data.
    """
    user = request.user
    visits_deleted, _ = PageVisit.objects.filter(user=user).delete()
    activities_deleted, _ = UserActivity.objects.filter(user=user).delete()

    messages.success(
        request,
        f"Deleted {visits_deleted} page visits and {activities_deleted} activity records."
    )
    return redirect("profile")


@staff_member_required
def tracking_dashboard(request):
    """
    Simple analytics dashboard for staff (superusers or users with permission).
    Shows top pages and daily visit counts for the last 7 days.
    """
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    top_pages = (
        PageVisit.objects.filter(timestamp__date__gte=week_ago)
        .values("page_url")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    daily_visits = (
        PageVisit.objects.filter(timestamp__date__gte=week_ago)
        .extra({"day": "date(timestamp)"})
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )

    context = {
        "top_pages": top_pages,
        "daily_visits": daily_visits,
        "total_visits_week": PageVisit.objects.filter(timestamp__date__gte=week_ago).count(),
        "unique_users_week": PageVisit.objects.filter(timestamp__date__gte=week_ago)
        .values("user")
        .distinct()
        .count(),
    }
    return render(request, "tracking/dashboard.html", context)