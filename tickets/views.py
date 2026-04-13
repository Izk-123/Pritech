from django.views.generic import ListView, CreateView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.db import models as db_models
from django import forms
from .models import Ticket, TicketComment
from .forms import TicketForm, CommentForm, WorkLogForm, AttachmentForm
from .services import TicketService
from core.mixins import HtmxMixin, RoleRequiredMixin


class TicketListView(LoginRequiredMixin, HtmxMixin, ListView):
    model = Ticket
    template_name = 'tickets/list.html'
    context_object_name = 'tickets'
    paginate_by = 20

    def get_queryset(self):
        qs = Ticket.objects.select_related('client', 'assigned_to', 'service')
        user = self.request.user

        # Clients see only tickets belonging to their own organization
        if user.user_type == 'client':
            if hasattr(user, 'client_organization'):
                qs = qs.filter(client=user.client_organization)
            else:
                return Ticket.objects.none()
        # Technicians (non‑admin) see assigned tickets + unassigned open tickets
        elif user.has_role('TECHNICIAN') and not user.has_role('ADMIN'):
            qs = qs.filter(
                db_models.Q(assigned_to=user) |
                db_models.Q(assigned_to__isnull=True, status='open')
            )

        # Apply filters from GET parameters
        status = self.request.GET.get('status')
        priority = self.request.GET.get('priority')
        q = self.request.GET.get('q')

        if status:
            qs = qs.filter(status=status)
        if priority:
            qs = qs.filter(priority=priority)
        if q:
            qs = qs.filter(
                db_models.Q(title__icontains=q) |
                db_models.Q(ticket_number__icontains=q)
            )

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Ticket.STATUS_CHOICES
        ctx['priority_choices'] = Ticket.PRIORITY_CHOICES
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['current_priority'] = self.request.GET.get('priority', '')
        ctx['current_q'] = self.request.GET.get('q', '')

        # Calculate counts for all statuses (staff see all, clients see only their org's tickets)
        user = self.request.user
        base_qs = Ticket.objects.all()
        if user.user_type == 'client' and hasattr(user, 'client_organization'):
            base_qs = base_qs.filter(client=user.client_organization)

        ctx['counts'] = {
            s[0]: base_qs.filter(status=s[0]).count()
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

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user = self.request.user
        # For clients, pre‑fill and hide the client field
        if user.user_type == 'client' and hasattr(user, 'client_organization'):
            form.fields['client'].initial = user.client_organization
            form.fields['client'].widget = forms.HiddenInput()
        return form

    def form_valid(self, form):
        # Use service layer to create ticket (and SLA)
        ticket = TicketService.create_ticket(
            title=form.cleaned_data['title'],
            description=form.cleaned_data['description'],
            client=form.cleaned_data['client'],
            service=form.cleaned_data.get('service'),
            priority=form.cleaned_data['priority'],
            created_by=self.request.user
        )
        messages.success(self.request, f'Ticket {ticket.ticket_number} created.')
        return redirect('ticket_detail', pk=ticket.pk)


class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = 'tickets/detail.html'
    context_object_name = 'ticket'

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        # Clients can only view their own organization's tickets
        if user.user_type == 'client':
            if hasattr(user, 'client_organization'):
                return qs.filter(client=user.client_organization)
            return qs.none()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['comment_form'] = CommentForm()
        ctx['worklog_form'] = WorkLogForm()
        ctx['attachment_form'] = AttachmentForm()
        ctx['comments'] = self.object.comments.select_related('author')
        ctx['worklogs'] = self.object.worklogs.select_related('technician')
        ctx['attachments'] = self.object.attachments.select_related('uploaded_by')
        ctx['sla'] = getattr(self.object, 'sla', None)
        ctx['next_statuses'] = self.object.VALID_TRANSITIONS.get(self.object.status, [])
        ctx['all_technicians'] = __import__('accounts.models', fromlist=['User']).User.objects.filter(user_type='staff')
        return ctx


class TicketTransitionView(RoleRequiredMixin, HtmxMixin, View):
    required_roles = ['TECHNICIAN', 'ADMIN']

    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        new_status = request.POST.get('status')
        note = request.POST.get('note', '')
        try:
            TicketService.transition(ticket, new_status, user=request.user, note=note)
            if self.is_htmx():
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


class AssignTicketView(RoleRequiredMixin, HtmxMixin, View):
    required_roles = ['TECHNICIAN', 'ADMIN']

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
                    {
                        'ticket': ticket,
                        'all_technicians': User.objects.filter(user_type='staff'),  # ← ADD THIS
                        'request': request
                    }
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


class AddWorkLogView(RoleRequiredMixin, HtmxMixin, View):
    required_roles = ['TECHNICIAN', 'ADMIN']

    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        form = WorkLogForm(request.POST)
        if form.is_valid():
            worklog = TicketService.log_work(
                ticket=ticket,
                technician=request.user,
                hours=form.cleaned_data['hours'],
                description=form.cleaned_data['description'],
            )
            if self.is_htmx():
                html = render_to_string(
                    'tickets/partials/worklog_item.html',
                    {'worklog': worklog}
                )
                return HttpResponse(html)
        return redirect('ticket_detail', pk=pk)


class AddAttachmentView(LoginRequiredMixin, HtmxMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        form = AttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            attachment = form.save(commit=False)
            attachment.ticket = ticket
            attachment.uploaded_by = request.user
            attachment.save()
            if self.is_htmx():
                html = render_to_string(
                    'tickets/partials/attachment_item.html',
                    {'attachment': attachment, 'request': request}
                )
                return HttpResponse(html)
        return redirect('ticket_detail', pk=pk)