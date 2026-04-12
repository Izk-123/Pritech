from django.views.generic import ListView, CreateView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from .models import Ticket, TicketComment
from .forms import TicketForm, CommentForm, WorkLogForm
from .services import TicketService
from core.mixins import HtmxMixin


class TicketListView(LoginRequiredMixin, HtmxMixin, ListView):
    model = Ticket
    template_name = 'tickets/list.html'
    context_object_name = 'tickets'
    paginate_by = 20

    def get_queryset(self):
        qs = Ticket.objects.select_related('client', 'assigned_to', 'service')
        status = self.request.GET.get('status')
        priority = self.request.GET.get('priority')
        q = self.request.GET.get('q')
        if status:
            qs = qs.filter(status=status)
        if priority:
            qs = qs.filter(priority=priority)
        if q:
            qs = qs.filter(title__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Ticket.STATUS_CHOICES
        ctx['priority_choices'] = Ticket.PRIORITY_CHOICES
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['current_priority'] = self.request.GET.get('priority', '')
        ctx['current_q'] = self.request.GET.get('q', '')
        ctx['counts'] = {
            s[0]: Ticket.objects.filter(status=s[0]).count()
            for s in Ticket.STATUS_CHOICES
        }
        return ctx

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        # HTMX partial: return only the table body
        if self.is_htmx():
            html = render_to_string(
                'tickets/partials/ticket_rows.html',
                {'tickets': self.get_queryset(), 'request': request}
            )
            return HttpResponse(html)
        return response


class TicketCreateView(LoginRequiredMixin, CreateView):
    model = Ticket
    form_class = TicketForm
    template_name = 'tickets/form.html'
    success_url = reverse_lazy('ticket_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f'Ticket #{self.object.pk} created.')
        return response


class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = 'tickets/detail.html'
    context_object_name = 'ticket'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['comment_form'] = CommentForm()
        ctx['worklog_form'] = WorkLogForm()
        ctx['comments'] = self.object.comments.select_related('author')
        ctx['worklogs'] = self.object.worklogs.select_related('technician')
        ctx['next_statuses'] = self.object.VALID_TRANSITIONS.get(self.object.status, [])
        ctx['all_technicians'] = __import__('accounts.models', fromlist=['User']).User.objects.filter(user_type='staff')
        return ctx


class TicketTransitionView(LoginRequiredMixin, HtmxMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        new_status = request.POST.get('status')
        note = request.POST.get('note', '')
        try:
            TicketService.transition(ticket, new_status, user=request.user, note=note)
            if self.is_htmx():
                # Return updated status badge + next actions
                html = render_to_string(
                    'tickets/partials/status_panel.html',
                    {'ticket': ticket, 'next_statuses': ticket.VALID_TRANSITIONS.get(ticket.status, []),
                     'request': request}
                )
                return HttpResponse(html)
            messages.success(request, f'Ticket moved to {new_status.replace("_", " ")}.')
        except ValueError as e:
            messages.error(request, str(e))
        return redirect('ticket_detail', pk=pk)


class AssignTicketView(LoginRequiredMixin, HtmxMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        from accounts.models import User
        tech_id = request.POST.get('technician_id')
        try:
            technician = User.objects.get(pk=tech_id, user_type='staff')
            TicketService.assign(ticket, technician, user=request.user)
            if self.is_htmx():
                html = render_to_string(
                    'tickets/partials/assignment_panel.html',
                    {'ticket': ticket, 'request': request}
                )
                return HttpResponse(html)
            messages.success(request, f'Assigned to {technician.get_full_name()}.')
        except Exception as e:
            messages.error(request, str(e))
        return redirect('ticket_detail', pk=pk)


class AddCommentView(LoginRequiredMixin, HtmxMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        form = CommentForm(request.POST)
        if form.is_valid():
            c = form.save(commit=False)
            c.ticket = ticket
            c.author = request.user
            c.save()
            if self.is_htmx():
                html = render_to_string(
                    'tickets/partials/comment.html',
                    {'comment': c, 'request': request}
                )
                return HttpResponse(html)
        return redirect('ticket_detail', pk=pk)


class AddWorkLogView(LoginRequiredMixin, HtmxMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        form = WorkLogForm(request.POST)
        if form.is_valid():
            TicketService.log_work(
                ticket=ticket,
                technician=request.user,
                hours=form.cleaned_data['hours'],
                description=form.cleaned_data['description'],
            )
            if self.is_htmx():
                return HttpResponse(
                    f'<div class="alert alert-success" style="margin:.5rem 0;">✓ {form.cleaned_data["hours"]}h logged.</div>'
                )
        return redirect('ticket_detail', pk=pk)
