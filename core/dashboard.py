# core/dashboard.py
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from clients.models import ClientOrganization
from tickets.models import Ticket
from finance.models import Payment, Invoice
from tracking.models import PageVisit

def dashboard_callback(request, context):
    print("!!! DASHBOARD_CALLBACK FIRED !!!", flush=True)
    now = timezone.now()
    today = now.date()

    context['dash_stats'] = {
        'total_clients': ClientOrganization.objects.count(),
        'active_clients': ClientOrganization.objects.filter(status='active').count(),
        'open_tickets': Ticket.objects.exclude(status__in=['closed', 'resolved']).count(),
        'overdue_tickets': Ticket.objects.filter(
            status__in=['open', 'assigned', 'in_progress'],
            sla__resolution_due__lt=now
        ).count(),
        'revenue_month': Payment.objects.filter(date__gte=today.replace(day=1)).aggregate(total=Sum('amount'))['total'] or 0,
        'invoiced_month': Invoice.objects.filter(issue_date__gte=today.replace(day=1)).aggregate(total=Sum('total_amount'))['total'] or 0,
    }

    days, tickets_per_day, visitors_per_day = [], [], []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        days.append(day.strftime('%a'))
        tickets_per_day.append(Ticket.objects.filter(created_at__date=day).count())
        visitors_per_day.append(PageVisit.objects.filter(timestamp__date=day).count())

    context['chart_data'] = {
        'weekdays': days,
        'tickets_per_day': tickets_per_day,
        'visitors_per_day': visitors_per_day,
    }

    context['recent_visits'] = PageVisit.objects.select_related('user')[:8]
    context['priority_stats'] = list(Ticket.objects.values('priority').annotate(count=Count('id')).order_by('priority'))
    return context