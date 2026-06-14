# accounts/views.py
"""
Main views for authentication, profile, team management, 2FA, staff admin, and analytics.
All new features (staff user management, role management, analytics, recovery codes) are included.
"""

from django.views.generic import CreateView, ListView, UpdateView, DeleteView, TemplateView, View
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import login
from django.urls import reverse, reverse_lazy
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.db.models.functions import TruncDay, TruncMonth
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import (
    User, Role, Permission, UserRole, EmailVerificationToken,
    InvitationToken, UserAuditLog, RecoveryCode, LoginEvent, UserSession
)
from .forms import (
    ClientRegisterForm, CustomLoginForm, ClientProfileForm,
    InviteTeamMemberForm, TOTPTokenForm, StaffUserCreationForm,
    StaffUserChangeForm, RoleForm, PermissionForm
)
from .utils import send_verification_email, parse_device
from .decorators import rate_limit, get_client_ip, client_role_required
from clients.models import ClientOrganization


# -----------------------------------------------------------------------------
# Registration & Email Verification
# -----------------------------------------------------------------------------

@method_decorator(rate_limit(key_func=get_client_ip, rate='5/h', method='POST', block=True), name='dispatch')
class ClientRegisterView(CreateView):
    """Client self‑registration with email verification."""
    model = User
    form_class = ClientRegisterForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        user = form.save(commit=False)
        user.set_password(form.cleaned_data['password'])
        user.user_type = 'client'
        user.username = form.cleaned_data['email']   # username = email for simplicity
        user.is_active = False                        # activate after email verification
        user.save()

        # Create client organisation
        org_name = form.cleaned_data['company_name']
        organization = ClientOrganization.objects.create(
            name=org_name,
            email=user.email,
            phone=form.cleaned_data.get('phone_number', ''),
            user=user,               # temporary – will be replaced by FK on User
            status='active'
        )
        # Link the user to the organisation (new FK)
        user.client_organization = organization
        user.save(update_fields=['client_organization'])

        # Assign default CLIENT role
        role, _ = Role.objects.get_or_create(code='CLIENT', defaults={'name': 'Client'})
        UserRole.objects.get_or_create(user=user, role=role)

        # Send verification email
        send_verification_email(user, self.request)

        messages.success(self.request, 'Account created! Please check your email to verify your account.')
        return redirect(self.success_url)


def verify_email(request, token):
    """Activate user account after email verification."""
    token_obj = get_object_or_404(EmailVerificationToken, token=token)
    if not token_obj.is_valid():
        messages.error(request, 'Verification link expired. Please register again.')
        return redirect('register')
    user = token_obj.user
    user.is_active = True
    user.save()
    token_obj.delete()
    messages.success(request, 'Email verified! You can now log in.')
    return redirect('login')


# -----------------------------------------------------------------------------
# Login / Logout with 2FA
# -----------------------------------------------------------------------------

@method_decorator(rate_limit(key_func=get_client_ip, rate='10/h', method='POST', block=True), name='dispatch')
class CustomLoginView(LoginView):
    """Login view with rate limiting and 2FA redirection."""
    form_class = CustomLoginForm
    template_name = 'accounts/login.html'

    def form_valid(self, form):
        user = form.get_user()
        if user and user.is_2fa_enabled:
            self.request.session['pre_2fa_user_id'] = str(user.pk)
            return redirect('two_factor_verify')
        return super().form_valid(form)


class TwoFactorVerifyView(View):
    """Verify TOTP code or recovery code after login."""
    template_name = 'accounts/two_factor_verify.html'

    def get(self, request):
        if not request.session.get('pre_2fa_user_id'):
            return redirect('login')
        form = TOTPTokenForm()
        return render(request, self.template_name, {'form': form, 'show_recovery': True})

    def post(self, request):
        user_id = request.session.get('pre_2fa_user_id')
        if not user_id:
            return redirect('login')
        user = get_object_or_404(User, pk=user_id)
        token = request.POST.get('token')

        # Try TOTP
        device = TOTPDevice.objects.filter(user=user, confirmed=True).first()
        if device and device.verify_token(token):
            login(request, user)
            del request.session['pre_2fa_user_id']
            return redirect(settings.LOGIN_REDIRECT_URL)

        # Try recovery code
        recovery = RecoveryCode.objects.filter(user=user, code=token, is_used=False).first()
        if recovery:
            recovery.is_used = True
            recovery.save()
            login(request, user)
            del request.session['pre_2fa_user_id']
            messages.warning(request, 'You used a recovery code. Please generate new ones in your profile.')
            return redirect(settings.LOGIN_REDIRECT_URL)

        messages.error(request, 'Invalid code.')
        return render(request, self.template_name, {'form': TOTPTokenForm(), 'show_recovery': True})


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('login')


# -----------------------------------------------------------------------------
# Profile & Client Self‑Service
# -----------------------------------------------------------------------------

class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/profile.html'


class ClientProfileEditView(LoginRequiredMixin, UpdateView):
    """Edit client profile and organisation details."""
    form_class = ClientProfileForm
    template_name = 'accounts/client_profile_edit.html'
    success_url = reverse_lazy('profile')

    def get_object(self, queryset=None):
        return self.request.user

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['client_org'] = self.request.user.client_organization
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Your profile has been updated.")
        return super().form_valid(form)


class ClientTeamListView(LoginRequiredMixin, ListView):
    """List all team members of the client's organisation."""
    model = User
    template_name = 'accounts/client_team.html'
    context_object_name = 'team_members'

    def get_queryset(self):
        client_org = self.request.user.client_organization
        if not client_org:
            return User.objects.none()
        return User.objects.filter(client_organization=client_org)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['can_invite'] = self.request.user.client_role == 'admin'
        return ctx


@method_decorator(client_role_required(['admin']), name='dispatch')
class ClientTeamInviteView(LoginRequiredMixin, View):
    """Send invitation email to add a team member."""
    def post(self, request):
        form = InviteTeamMemberForm(request.POST, client_org=request.user.client_organization)
        if form.is_valid():
            email = form.cleaned_data['email']
            role = form.cleaned_data['role']
            token = InvitationToken.objects.create(
                email=email,
                client_organization=request.user.client_organization,
                role=role
            )
            invite_url = request.build_absolute_uri(reverse('accept_invite', args=[token.token]))
            send_mail(
                subject=f"Invitation to join {request.user.client_organization.name} on PriTech",
                message=f"Click the link to accept: {invite_url}\n\nThis link expires in 7 days.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            messages.success(request, f"Invitation sent to {email}.")
        else:
            messages.error(request, "Please correct the errors.")
        return redirect('client_team')


@method_decorator(client_role_required(['admin']), name='dispatch')
class ClientTeamRemoveView(LoginRequiredMixin, View):
    """Remove a team member from the organisation."""
    def post(self, request, user_id):
        user_to_remove = get_object_or_404(User, pk=user_id, client_organization=request.user.client_organization)
        if user_to_remove == request.user:
            messages.error(request, "You cannot remove yourself.")
            return redirect('client_team')
        user_to_remove.delete()
        messages.success(request, f"Removed {user_to_remove.email} from your organisation.")
        return redirect('client_team')


class ClientAuditLogView(LoginRequiredMixin, ListView):
    """Audit log for the client's organisation."""
    model = UserAuditLog
    template_name = 'accounts/client_audit_log.html'
    context_object_name = 'logs'
    paginate_by = 50

    def get_queryset(self):
        client_org = self.request.user.client_organization
        if not client_org:
            return UserAuditLog.objects.none()
        user_ids = User.objects.filter(client_organization=client_org).values_list('id', flat=True)
        return UserAuditLog.objects.filter(user_id__in=user_ids).select_related('user').order_by('-timestamp')


def accept_invite(request, token):
    """Accept an invitation token, create or link user to organisation."""
    token_obj = get_object_or_404(InvitationToken, token=token)
    if not token_obj.is_valid():
        messages.error(request, "Invitation expired. Please ask for a new one.")
        return redirect('login')

    user = User.objects.filter(email=token_obj.email).first()
    if user:
        user.client_organization = token_obj.client_organization
        user.client_role = token_obj.role
        user.save(update_fields=['client_organization', 'client_role'])
        messages.success(request, f"You've joined {token_obj.client_organization.name}. You can now log in.")
    else:
        temp_password = User.objects.make_random_password(length=12)
        user = User.objects.create_user(
            username=token_obj.email,
            email=token_obj.email,
            password=temp_password,
            first_name='',
            last_name='',
            user_type='client',
            client_organization=token_obj.client_organization,
            client_role=token_obj.role,
            is_active=True
        )
        messages.success(request, f"You've joined {token_obj.client_organization.name}. Please use 'Forgot password' to set your password.")
    token_obj.delete()
    return redirect('login')


# -----------------------------------------------------------------------------
# Staff User Management (admin only)
# -----------------------------------------------------------------------------

@method_decorator(staff_member_required, name='dispatch')
class UserListView(ListView):
    model = User
    template_name = 'accounts/staff_user_list.html'
    context_object_name = 'users'
    paginate_by = 50

    def get_queryset(self):
        qs = User.objects.all().prefetch_related('user_roles__role')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
        user_type = self.request.GET.get('user_type')
        if user_type:
            qs = qs.filter(user_type=user_type)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['user_type_choices'] = User.USER_TYPE_CHOICES
        return ctx


@method_decorator(staff_member_required, name='dispatch')
class UserCreateView(CreateView):
    model = User
    form_class = StaffUserCreationForm
    template_name = 'accounts/staff_user_form.html'
    success_url = reverse_lazy('accounts:user_list')

    def form_valid(self, form):
        user = form.save(commit=False)
        user.set_password(form.cleaned_data['password1'])
        user.save()
        roles = form.cleaned_data.get('roles', [])
        for role in roles:
            UserRole.objects.get_or_create(user=user, role=role)
        messages.success(self.request, f"User {user.email} created.")
        return super().form_valid(form)


@method_decorator(staff_member_required, name='dispatch')
class UserUpdateView(UpdateView):
    model = User
    form_class = StaffUserChangeForm
    template_name = 'accounts/staff_user_form.html'
    success_url = reverse_lazy('accounts:user_list')

    def get_initial(self):
        initial = super().get_initial()
        initial['roles'] = UserRole.objects.filter(user=self.object).values_list('role_id', flat=True)
        return initial

    def form_valid(self, form):
        user = form.save()
        new_role_ids = set(form.cleaned_data['roles'].values_list('id', flat=True))
        current_role_ids = set(UserRole.objects.filter(user=user).values_list('role_id', flat=True))
        to_add = new_role_ids - current_role_ids
        to_remove = current_role_ids - new_role_ids
        for role_id in to_add:
            UserRole.objects.get_or_create(user=user, role_id=role_id)
        for role_id in to_remove:
            UserRole.objects.filter(user=user, role_id=role_id).delete()
        messages.success(self.request, f"User {user.email} updated.")
        return super().form_valid(form)


@method_decorator(staff_member_required, name='dispatch')
class UserDeleteView(DeleteView):
    model = User
    template_name = 'accounts/staff_user_confirm_delete.html'
    success_url = reverse_lazy('accounts:user_list')

    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        if user.is_superuser:
            messages.error(request, "Cannot delete superuser.")
            return redirect('accounts:user_list')
        messages.success(request, f"User {user.email} deleted.")
        return super().delete(request, *args, **kwargs)
    
@method_decorator(staff_member_required, name='dispatch')
class StaffListView(LoginRequiredMixin, ListView):
    """List all staff users (internal use)."""
    model = User
    template_name = 'accounts/staff_list.html'
    context_object_name = 'staff'

    def get_queryset(self):
        return User.objects.filter(user_type='staff').prefetch_related('user_roles__role')


# -----------------------------------------------------------------------------
# Role Management (staff only)
# -----------------------------------------------------------------------------

@method_decorator(staff_member_required, name='dispatch')
class RoleListView(ListView):
    model = Role
    template_name = 'accounts/role_list.html'
    context_object_name = 'roles'


@method_decorator(staff_member_required, name='dispatch')
class RoleCreateView(CreateView):
    model = Role
    form_class = RoleForm
    template_name = 'accounts/role_form.html'
    success_url = reverse_lazy('accounts:role_list')


@method_decorator(staff_member_required, name='dispatch')
class RoleUpdateView(UpdateView):
    model = Role
    form_class = RoleForm
    template_name = 'accounts/role_form.html'
    success_url = reverse_lazy('accounts:role_list')


@method_decorator(staff_member_required, name='dispatch')
class RoleDeleteView(DeleteView):
    model = Role
    template_name = 'accounts/role_confirm_delete.html'
    success_url = reverse_lazy('accounts:role_list')


# -----------------------------------------------------------------------------
# Permission Management (optional)
# -----------------------------------------------------------------------------

@method_decorator(staff_member_required, name='dispatch')
class PermissionListView(ListView):
    model = Permission
    template_name = 'accounts/permission_list.html'
    context_object_name = 'permissions'


@method_decorator(staff_member_required, name='dispatch')
class PermissionCreateView(CreateView):
    model = Permission
    form_class = PermissionForm
    template_name = 'accounts/permission_form.html'
    success_url = reverse_lazy('accounts:permission_list')


@method_decorator(staff_member_required, name='dispatch')
class PermissionUpdateView(UpdateView):
    model = Permission
    form_class = PermissionForm
    template_name = 'accounts/permission_form.html'
    success_url = reverse_lazy('accounts:permission_list')


@method_decorator(staff_member_required, name='dispatch')
class PermissionDeleteView(DeleteView):
    model = Permission
    template_name = 'accounts/permission_confirm_delete.html'
    success_url = reverse_lazy('accounts:permission_list')


# -----------------------------------------------------------------------------
# Analytics Dashboard
# -----------------------------------------------------------------------------

@method_decorator(staff_member_required, name='dispatch')
class AnalyticsView(TemplateView):
    template_name = 'accounts/analytics.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        last_30_days = now - timedelta(days=30)

        # Login statistics
        login_stats = LoginEvent.objects.filter(timestamp__gte=last_30_days).values('event_type').annotate(count=Count('id'))
        ctx['login_stats'] = {item['event_type']: item['count'] for item in login_stats}

        # Daily logins chart
        daily_logins = LoginEvent.objects.filter(event_type='success', timestamp__gte=last_30_days) \
            .annotate(day=TruncDay('timestamp')).values('day').annotate(count=Count('id')).order_by('day')
        ctx['daily_logins'] = list(daily_logins)

        # Monthly user growth
        monthly_growth = User.objects.annotate(month=TruncMonth('date_joined')).values('month').annotate(count=Count('id')).order_by('month')
        ctx['monthly_growth'] = list(monthly_growth)

        # Active users now (last 30 minutes)
        active_threshold = now - timedelta(minutes=30)
        active_sessions = UserSession.objects.filter(last_activity__gte=active_threshold, is_active=True).values('user').distinct().count()
        ctx['active_users_now'] = active_sessions

        # Device statistics
        device_stats = UserSession.objects.filter(login_time__gte=last_30_days).values('device').annotate(count=Count('id')).order_by('-count')
        ctx['device_stats'] = device_stats

        # Cumulative user growth
        users_by_day = User.objects.annotate(day=TruncDay('date_joined')).values('day').annotate(count=Count('id')).order_by('day')
        cumulative = []
        total = 0
        for item in users_by_day:
            total += item['count']
            cumulative.append({'day': item['day'], 'total': total})
        ctx['cumulative_users'] = cumulative

        return ctx


# -----------------------------------------------------------------------------
# Recovery Codes (for 2FA)
# -----------------------------------------------------------------------------

@login_required
def recovery_codes_view(request):
    """Display and regenerate recovery codes."""
    user = request.user
    codes = RecoveryCode.objects.filter(user=user, is_used=False)
    if request.method == 'POST':
        RecoveryCode.objects.filter(user=user).delete()
        RecoveryCode.generate_for_user(user)
        messages.success(request, "New recovery codes generated.")
        return redirect('accounts:recovery_codes')
    return render(request, 'accounts/recovery_codes.html', {'codes': codes})