# core/htmx_views.py
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from tickets.models import Ticket

@staff_member_required
def ticket_search(request):
    query = request.GET.get('q', '')
    tickets = Ticket.objects.filter(
        Q(ticket_number__icontains=query) | Q(title__icontains=query)
    )[:20]
    html = render_to_string('admin/partials/ticket_rows.html', {'tickets': tickets})
    return HttpResponse(html)

@staff_member_required
def update_ticket_status(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if ticket.can_transition_to(new_status):
            ticket.status = new_status
            ticket.save()
        return HttpResponse(ticket.get_status_display())
    return HttpResponse(status=405)