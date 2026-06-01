# accounts/views.py
from django.views.generic import CreateView, ListView, UpdateView, TemplateView, View
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse, reverse_lazy
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib import messages
from django.db import transaction
from django.utils.decorators import method_decorator
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import login
from django.views import View
from django_otp.plugins.otp_totp.models import TOTPDevice
from .models import User, Role, UserRole, EmailVerificationToken, InvitationToken
from .forms import ClientRegisterForm, CustomLoginForm, ClientProfileForm, InviteTeamMemberForm, TOTPTokenForm
from .utils import send_verification_email
from .decorators import rate_limit, get_client_ip, client_role_required
from clients.models import ClientOrganization
from accounts.models import UserAuditLog


# ---------- Registration with email verification & rate limiting ----------
@method_decorator(rate_limit(key_func=get_client_ip, rate='5/h', method='POST', block=True), name='dispatch')
class ClientRegisterView(CreateView):
    model = User
    form_class = ClientRegisterForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        user = form.save(commit=False)
        user.set_password(form.cleaned_data['password'])
        user.user_type = 'client'
        user.username = form.cleaned_data['email']
        user.is_active = False
        user.save()

        # Create client organization
        org_name = form.cleaned_data.get('company_name') or user.email.split('@')[0]
        organization = ClientOrganization.objects.create(
            name=org_name,
            email=user.email,
            phone=form.cleaned_data.get('phone_number', ''),
            user=user,
            status='active'
        )

        # Assign CLIENT role
        role, _ = Role.objects.get_or_create(code='CLIENT', defaults={'name': 'Client'})
        UserRole.objects.create(user=user, role=role)

        # Send verification email
        send_verification_email(user, self.request)

        messages.success(self.request, 'Account created! Please check your email to verify your account.')
        return redirect(self.success_url)


# ---------- Email verification ----------
def verify_email(request, token):
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


# ---------- Login with rate limiting ----------
@method_decorator(rate_limit(key_func=get_client_ip, rate='10/h', method='POST', block=True), name='dispatch')
class CustomLoginView(LoginView):
    form_class = CustomLoginForm
    template_name = 'accounts/login.html'

    def form_valid(self, form):
        # Get the authenticated user (already checked by LoginView)
        user = form.get_user()
        if user and user.is_2fa_enabled:
            # Store user ID in session and redirect to 2FA verification
            self.request.session['pre_2fa_user_id'] = user.pk
            return redirect('two_factor_verify')
        return super().form_valid(form)


class TwoFactorVerifyView(View):
    template_name = 'accounts/two_factor_verify.html'

    def get(self, request):
        user_id = request.session.get('pre_2fa_user_id')
        if not user_id:
            return redirect('login')
        form = TOTPTokenForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        user_id = request.session.get('pre_2fa_user_id')
        if not user_id:
            return redirect('login')
        user = get_object_or_404(User, pk=user_id)
        form = TOTPTokenForm(request.POST)
        if form.is_valid():
            token = form.cleaned_data['token']
            device = TOTPDevice.objects.filter(user=user, confirmed=True).first()
            if device and device.verify_token(token):
                login(request, user)
                # Clean up session
                del request.session['pre_2fa_user_id']
                return redirect(settings.LOGIN_REDIRECT_URL)
            else:
                messages.error(request, 'Invalid two‑factor authentication code.')
        return render(request, self.template_name, {'form': form})


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('login')


# ---------- Staff list (for internal use) ----------
class StaffListView(LoginRequiredMixin, ListView):
    model = User
    template_name = 'accounts/staff_list.html'
    context_object_name = 'staff'

    def get_queryset(self):
        return User.objects.filter(user_type='staff').prefetch_related('user_roles__role')


# ---------- Profile view (read‑only) ----------
class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/profile.html'


# ---------- Client Self‑Service Views ----------
class ClientTeamListView(LoginRequiredMixin, ListView):
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
    def post(self, request):
        form = InviteTeamMemberForm(request.POST, client_org=request.user.client_organization)
        if form.is_valid():
            email = form.cleaned_data['email']
            role = form.cleaned_data['role']
            # Create invitation token
            token = InvitationToken.objects.create(
                email=email,
                client_organization=request.user.client_organization,
                role=role
            )
            # Send invitation email
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
    def post(self, request, user_id):
        user_to_remove = get_object_or_404(User, pk=user_id, client_organization=request.user.client_organization)
        if user_to_remove == request.user:
            messages.error(request, "You cannot remove yourself.")
            return redirect('client_team')
        user_to_remove.delete()
        messages.success(request, f"Removed {user_to_remove.email} from your organization.")
        return redirect('client_team')


class ClientProfileEditView(LoginRequiredMixin, UpdateView):
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


class ClientAuditLogView(LoginRequiredMixin, ListView):
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


# ---------- Accept invitation ----------
def accept_invite(request, token):
    token_obj = get_object_or_404(InvitationToken, token=token)
    if not token_obj.is_valid():
        messages.error(request, "Invitation expired. Please ask for a new one.")
        return redirect('login')

    # Check if user already exists
    user = User.objects.filter(email=token_obj.email).first()
    if user:
        # Link existing user to organization
        user.client_organization = token_obj.client_organization
        user.client_role = token_obj.role
        user.save()
        messages.success(request, f"You've joined {token_obj.client_organization.name}. You can now log in.")
    else:
        # Create new user with random password (they will reset via password reset)
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