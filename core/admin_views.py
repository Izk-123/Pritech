from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.db.models import Q
from tickets.models import Ticket
from .dashboard import dashboard_callback   # if you still want stats

@staff_member_required
def htmx_admin_index(request, extra_context=None):
    context = {}
    # Optionally add your KPIs via the existing callback
    try:
        dashboard_callback(request, context)
    except:
        pass
    
    # Initial tickets for the table
    tickets = Ticket.objects.all().order_by('-created_at')[:20]
    context['tickets'] = tickets
    context['title'] = 'Dashboard'
    return render(request, 'admin/htmx_index.html', context)

@staff_member_required
def admin_live_ticket_search(request):
    query = request.GET.get('q', '')
    tickets = Ticket.objects.filter(
        Q(ticket_number__icontains=query) | Q(title__icontains=query)
    )[:20]
    html = render_to_string('admin/ticket_rows.html', {'tickets': tickets})
    return HttpResponse(html)

@staff_member_required
def admin_inline_ticket_status(request, ticket_id):
    if request.method == 'POST':
        ticket = Ticket.objects.get(pk=ticket_id)
        new_status = request.POST.get('status')
        if ticket.can_transition_to(new_status):
            ticket.status = new_status
            ticket.save()
        return HttpResponse(ticket.get_status_display())
    return HttpResponse(status=405)