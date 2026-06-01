# tickets/views.py
"""
Tickets App Views
-----------------
Handles ticket listing, creation, detail view, status transitions, assignments,
comments, work logs, attachments, bulk actions, and canned responses.
Includes all security fixes (permissions, rate limiting, sanitization, validation).
"""

import json
import os
import mimetypes
from decimal import Decimal

from django.views.generic import ListView, CreateView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.template.loader import render_to_string
from django.db import models as db_models
from django.db.models import Exists, OuterRef, Q, Sum
from django import forms
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils import timezone

from .models import Ticket, TicketComment, TicketWorkLog, CannedResponse
from .forms import TicketForm, CommentForm, WorkLogForm, AttachmentForm
from .services import TicketService
from core.mixins import HtmxMixin, RoleRequiredMixin
from accounts.decorators import rate_limit, get_client_ip
from infrastructure.pdf_sanitizer import sanitize_html


# =============================================================================
# Helper class for sanitized Quill content
# =============================================================================
class SanitizedQuill:
    """Wrapper for Quill HTML that has been sanitized."""
    def __init__(self, html):
        self.html = html


# =============================================================================
# Ticket List & Creation
# =============================================================================

class TicketListView(LoginRequiredMixin, HtmxMixin, ListView):
    """
    List tickets with filtering and HTMX support.
    Search includes title, ticket number, description, and comment content.
    """
    model = Ticket
    template_name = 'tickets/list.html'
    context_object_name = 'tickets'
    paginate_by = 20

    def get_queryset(self):
        qs = Ticket.objects.select_related('client', 'assigned_to', 'service')
        user = self.request.user

        if user.user_type == 'client':
            if hasattr(user, 'client_organization'):
                qs = qs.filter(client=user.client_organization)
            else:
                return Ticket.objects.none()
        elif user.has_role('TECHNICIAN') and not user.has_role('ADMIN'):
            qs = qs.filter(
                Q(assigned_to=user) | Q(assigned_to__isnull=True, status='open')
            )

        status = self.request.GET.get('status')
        priority = self.request.GET.get('priority')
        q = self.request.GET.get('q')

        if status:
            qs = qs.filter(status=status)
        if priority:
            qs = qs.filter(priority=priority)
        if q:
            comment_exists = TicketComment.objects.filter(
                ticket=OuterRef('pk'), content__icontains=q
            )
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(ticket_number__icontains=q) |
                Q(description__icontains=q) |
                Exists(comment_exists)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Ticket.STATUS_CHOICES
        ctx['priority_choices'] = Ticket.PRIORITY_CHOICES
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['current_priority'] = self.request.GET.get('priority', '')
        ctx['current_q'] = self.request.GET.get('q', '')

        user = self.request.user
        base_qs = Ticket.objects.all()
        if user.user_type == 'client' and hasattr(user, 'client_organization'):
            base_qs = base_qs.filter(client=user.client_organization)
        ctx['counts'] = {s[0]: base_qs.filter(status=s[0]).count() for s in Ticket.STATUS_CHOICES}
        return ctx

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        if self.is_htmx():
            html = render_to_string(
                'tickets/partials/ticket_rows.html',
                {'tickets': self.get_queryset(), 'request': request}
            )
            return HttpResponse(html)
        return response


class TicketCreateView(LoginRequiredMixin, CreateView):
    """Create a new ticket. Clients have client field pre‑filled and hidden."""
    model = Ticket
    form_class = TicketForm
    template_name = 'tickets/form.html'
    success_url = reverse_lazy('ticket_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user = self.request.user
        if user.user_type == 'client' and hasattr(user, 'client_organization'):
            form.fields['client'].initial = user.client_organization
            form.fields['client'].widget = forms.HiddenInput()
        return form

    def form_valid(self, form):
        description_raw = form.cleaned_data['description']
        description_json = json.dumps({"html": f"<p>{description_raw}</p>", "delta": ""})
        ticket = TicketService.create_ticket(
            title=form.cleaned_data['title'],
            description=description_json,
            client=form.cleaned_data['client'],
            service=form.cleaned_data.get('service'),
            priority=form.cleaned_data['priority'],
            created_by=self.request.user
        )
        messages.success(self.request, f'Ticket {ticket.ticket_number} created.')
        return redirect('ticket_detail', pk=ticket.pk)


# =============================================================================
# Ticket Detail & Actions (Transition, Assignment)
# =============================================================================

class TicketDetailView(LoginRequiredMixin, DetailView):
    """
    Display ticket details with sanitized Quill content,
    paginated comments, and canned responses.
    """
    model = Ticket
    template_name = 'tickets/detail.html'
    context_object_name = 'ticket'

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.user_type == 'client':
            if hasattr(user, 'client_organization'):
                return qs.filter(client=user.client_organization)
            return qs.none()
        return qs

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        user = self.request.user
        if user.user_type == 'client':
            client_org = getattr(user, 'client_organization', None)
            if not client_org or obj.client != client_org:
                raise Http404("Ticket not found.")
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Sanitize description (Quill field)
        if self.object.description and hasattr(self.object.description, 'html'):
            raw_html = self.object.description.html
            if raw_html:
                sanitized = sanitize_html(raw_html)
                self.object.description = SanitizedQuill(sanitized)

        # Paginate comments (20 per page)
        all_comments = self.object.comments.select_related('author').order_by('created_at')
        page = self.request.GET.get('comments_page', 1)
        paginator = Paginator(all_comments, 20)
        try:
            comments_page = paginator.page(page)
        except PageNotAnInteger:
            comments_page = paginator.page(1)
        except EmptyPage:
            comments_page = paginator.page(paginator.num_pages)

        # Sanitize comments
        for c in comments_page:
            if c.content and hasattr(c.content, 'html'):
                raw_html = c.content.html
                if raw_html:
                    c.content = SanitizedQuill(sanitize_html(raw_html))
        ctx['comments'] = comments_page
        ctx['comments_paginator'] = paginator

        # Sanitize work logs
        worklogs = []
        for w in self.object.worklogs.select_related('technician'):
            if w.description and hasattr(w.description, 'html'):
                raw_html = w.description.html
                if raw_html:
                    w.description = SanitizedQuill(sanitize_html(raw_html))
            worklogs.append(w)
        ctx['worklogs'] = worklogs

        ctx['comment_form'] = CommentForm()
        ctx['worklog_form'] = WorkLogForm()
        ctx['attachment_form'] = AttachmentForm()
        ctx['attachments'] = self.object.attachments.select_related('uploaded_by')
        ctx['sla'] = getattr(self.object, 'sla', None)
        ctx['next_statuses'] = self.object.VALID_TRANSITIONS.get(self.object.status, [])
        from accounts.models import User
        ctx['all_technicians'] = User.objects.filter(user_type='staff')
        ctx['canned_responses'] = CannedResponse.objects.filter(is_active=True)
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
                    {'ticket': ticket, 'all_technicians': User.objects.filter(user_type='staff'),
                     'request': request}
                )
                return HttpResponse(html)
            messages.success(request, f'Assigned to {technician.get_full_name()}.')
        except Exception as e:
            messages.error(request, str(e))
        return redirect('ticket_detail', pk=pk)


# =============================================================================
# Comments, Work Logs, Attachments – with Security and Validation
# =============================================================================

@method_decorator(rate_limit(key_func=get_client_ip, rate='10/m', method='POST', block=True), name='dispatch')
class AddCommentView(LoginRequiredMixin, HtmxMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)

        user = request.user
        client_org = getattr(user, 'client_organization', None)
        is_staff = user.is_staff or user.user_type == 'staff'
        is_owner = client_org and ticket.client == client_org
        is_assigned = ticket.assigned_to == user

        if not (is_staff or is_owner or is_assigned):
            return HttpResponseForbidden("You do not have permission to comment on this ticket.")

        content_raw = request.POST.get('content')
        is_internal = request.POST.get('is_internal') == 'on'

        if is_internal and not is_staff:
            is_internal = False

        if not content_raw:
            messages.error(request, "Comment cannot be empty.")
            return redirect('ticket_detail', pk=pk)

        content_json = json.dumps({
            "html": f"<p>{content_raw.replace('<', '&lt;').replace('>', '&gt;')}</p>",
            "delta": ""
        })

        comment = TicketComment.objects.create(
            ticket=ticket,
            author=request.user,
            content=content_json,
            is_internal=is_internal
        )

        if self.is_htmx():
            html = render_to_string('tickets/partials/comment.html', {'comment': comment, 'request': request})
            return HttpResponse(html)
        return redirect('ticket_detail', pk=pk)


@method_decorator(rate_limit(key_func=get_client_ip, rate='5/m', method='POST', block=True), name='dispatch')
class AddWorkLogView(RoleRequiredMixin, HtmxMixin, View):
    required_roles = ['TECHNICIAN', 'ADMIN']

    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)

        user = request.user
        if user.user_type == 'staff' and not user.is_superuser:
            if ticket.assigned_to and ticket.assigned_to != user:
                messages.error(request, "You can only log work on tickets assigned to you.")
                return redirect('ticket_detail', pk=pk)

        hours = Decimal(request.POST.get('hours', 0))
        if hours > 24:
            messages.error(request, "Cannot log more than 24 hours in a single entry.")
            return redirect('ticket_detail', pk=pk)

        # Check total hours for this technician on this ticket today
        today = timezone.now().date()
        today_hours = TicketWorkLog.objects.filter(
            ticket=ticket,
            technician=user,
            logged_at__date=today
        ).aggregate(total=Sum('hours'))['total'] or 0

        if today_hours + hours > 24:
            messages.error(request, f"You have already logged {today_hours} hours today. Maximum 24 hours per day.")
            return redirect('ticket_detail', pk=pk)

        description_raw = request.POST.get('description')
        if not description_raw:
            messages.error(request, "Description is required.")
            return redirect('ticket_detail', pk=pk)

        description_json = json.dumps({
            "html": f"<p>{description_raw.replace('<', '&lt;').replace('>', '&gt;')}</p>",
            "delta": ""
        })

        worklog = TicketService.log_work(
            ticket=ticket,
            technician=user,
            hours=hours,
            description=description_json
        )

        if self.is_htmx():
            html = render_to_string('tickets/partials/worklog_item.html', {'worklog': worklog})
            return HttpResponse(html)
        return redirect('ticket_detail', pk=pk)


@method_decorator(rate_limit(key_func=get_client_ip, rate='5/m', method='POST', block=True), name='dispatch')
class AddAttachmentView(LoginRequiredMixin, HtmxMixin, View):
    ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.txt', '.doc', '.docx']
    MAX_FILE_SIZE = 5 * 1024 * 1024

    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)

        user = request.user
        client_org = getattr(user, 'client_organization', None)
        is_staff = user.is_staff or user.user_type == 'staff'
        is_owner = client_org and ticket.client == client_org
        is_assigned = ticket.assigned_to == user

        if not (is_staff or is_owner or is_assigned):
            return HttpResponseForbidden("You do not have permission to upload attachments to this ticket.")

        form = AttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            if uploaded_file.size > self.MAX_FILE_SIZE:
                messages.error(request, f"File too large. Maximum size is {self.MAX_FILE_SIZE // (1024*1024)} MB.")
                return redirect('ticket_detail', pk=pk)

            ext = os.path.splitext(uploaded_file.name)[1].lower()
            if ext not in self.ALLOWED_EXTENSIONS:
                messages.error(request, f"File type '{ext}' is not allowed.")
                return redirect('ticket_detail', pk=pk)

            mime_type, _ = mimetypes.guess_type(uploaded_file.name)
            if mime_type and not mime_type.startswith(('image/', 'application/pdf', 'text/plain', 'application/msword', 'application/vnd.openxmlformats-officedocument')):
                messages.error(request, f"File content type '{mime_type}' not allowed.")
                return redirect('ticket_detail', pk=pk)

            attachment = form.save(commit=False)
            attachment.ticket = ticket
            attachment.uploaded_by = user
            attachment.save()

            if self.is_htmx():
                html = render_to_string('tickets/partials/attachment_item.html', {'attachment': attachment, 'request': request})
                return HttpResponse(html)
        return redirect('ticket_detail', pk=pk)


# =============================================================================
# Bulk Actions & Canned Responses
# =============================================================================

class BulkTicketActionView(RoleRequiredMixin, View):
    required_roles = ['TECHNICIAN', 'ADMIN']

    def post(self, request):
        action = request.POST.get('action')
        ticket_ids = request.POST.getlist('ticket_ids')
        if not ticket_ids:
            messages.error(request, 'No tickets selected.')
            return redirect(request.META.get('HTTP_REFERER', 'ticket_list'))

        tickets = Ticket.objects.filter(pk__in=ticket_ids)
        if action == 'close':
            count = 0
            for ticket in tickets:
                if ticket.can_transition_to('closed'):
                    ticket.status = 'closed'
                    ticket.save()
                    count += 1
            messages.success(request, f'{count} ticket(s) closed.')
        else:
            messages.error(request, 'Invalid action.')
        return redirect(request.META.get('HTTP_REFERER', 'ticket_list'))


class MarkSolutionView(RoleRequiredMixin, View):
    required_roles = ['TECHNICIAN', 'ADMIN']

    def post(self, request, pk, comment_id):
        ticket = get_object_or_404(Ticket, pk=pk)
        comment = get_object_or_404(TicketComment, pk=comment_id, ticket=ticket)
        # Remove previous solution flag from this ticket
        TicketComment.objects.filter(ticket=ticket, is_solution=True).update(is_solution=False)
        comment.is_solution = True
        comment.save()
        messages.success(request, "Comment marked as solution.")
        return redirect('ticket_detail', pk=pk)