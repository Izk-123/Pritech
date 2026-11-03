# accounts/views.py
"""
Views for the Accounts app.

This module handles:
  - Client registration & email verification
  - Login / Logout / 2FA
  - Profile & team management
  - Staff user administration
  - Roles, Permissions & Analytics

── Notes on recent fixes ──
* UserUpdateView: Now correctly processes and saves password changes 
  (password1/password2) if provided by the admin. Includes form_invalid
  overrides to show a top-level error banner.
* UserCreateView: Form_invalid override added to show a global error message.
* UserDeleteView: Added a robust dispatch() guard to prevent deletion of
  staff/superusers (defense-in-depth).
"""

from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.db.models.functions import TruncDay, TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)
from django_otp.plugins.otp_totp.models import TOTPDevice

from clients.models import ClientOrganization

from .decorators import client_role_required, get_client_ip, rate_limit
from .forms import (
    ClientProfileForm,
    ClientRegisterForm,
    CustomLoginForm,
    InviteTeamMemberForm,
    PermissionForm,
    RoleForm,
    StaffUserChangeForm,
    StaffUserCreationForm,
    TOTPTokenForm,
)
from .models import (
    EmailVerificationToken,
    InvitationToken,
    LoginEvent,
    Permission,
    RecoveryCode,
    Role,
    User,
    UserAuditLog,
    UserRole,
    UserSession,
)
from .utils import (
    parse_device,
    send_verification_email,
    sync_allauth_email,
)


# =============================================================================
# 1. Registration & Email Verification
# =============================================================================

@method_decorator(
    rate_limit(key_func=get_client_ip, rate="5/h", method="POST", block=True),
    name="dispatch",
)
class ClientRegisterView(CreateView):
    model = User
    form_class = ClientRegisterForm
    template_name = "accounts/register.html"

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors highlighted below.")
        return super().form_invalid(form)

    def form_valid(self, form):
        user = form.save(commit=False)
        user.set_password(form.cleaned_data["password"])
        user.user_type = "client"
        user.username = form.cleaned_data["email"]
        user.is_active = False
        user.save()

        organization = ClientOrganization.objects.create(
            name=form.cleaned_data["company_name"],
            email=user.email,
            phone=form.cleaned_data.get("phone_number", ""),
            user=user,
            status="active",
        )
        user.client_organization = organization
        user.save(update_fields=["client_organization"])

        role, _ = Role.objects.get_or_create(code="CLIENT", defaults={"name": "Client"})
        UserRole.objects.get_or_create(user=user, role=role)

        try:
            send_verification_email(user, self.request)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Verification email failed for %s", user.email)
            messages.error(
                self.request,
                "Your account was created but we could not send the verification email. "
                "Please use the resend link on the next page.",
            )

        self.request.session["pending_verification_email"] = user.email
        messages.success(
            self.request,
            "Account created. Check your inbox to verify your email and activate your account.",
        )
        return redirect("check_your_email")


def verify_email(request, token):
    token_obj = EmailVerificationToken.objects.select_related("user").filter(token=token).first()

    if token_obj is None:
        messages.error(request, "This verification link is invalid or has already been used.")
        return redirect("login")

    user = token_obj.user

    if user.is_active:
        sync_allauth_email(user, verified=True)
        token_obj.delete()
        messages.info(request, "Your email is already verified. Please log in.")
        return redirect("login")

    if not token_obj.is_valid():
        return render(request, "accounts/verification_expired.html", {"email": user.email})

    user.is_active = True
    user.save(update_fields=["is_active"])
    sync_allauth_email(user, verified=True)
    token_obj.delete()

    if request.session.get("pending_verification_email") == user.email:
        request.session.pop("pending_verification_email", None)

    messages.success(request, "Email verified! You can now log in to your account.")
    return redirect("login")


class CheckYourEmailView(TemplateView):
    template_name = "accounts/check_your_email.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["email"] = self.request.session.get("pending_verification_email", "")
        return ctx


@method_decorator(
    rate_limit(key_func=get_client_ip, rate="3/h", method="POST", block=True),
    name="dispatch",
)
class ResendVerificationView(View):
    def post(self, request):
        email = (request.POST.get("email") or "").strip().lower()

        if email:
            pending_user = User.objects.filter(email__iexact=email, is_active=False).first()
            if pending_user:
                try:
                    send_verification_email(pending_user, request, resend=True)
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception("Resend verification failed for %s", email)
            request.session["pending_verification_email"] = email

        messages.success(
            request,
            "If that email matches an unverified account, a new verification link is on its way.",
        )
        return redirect("check_your_email")


# =============================================================================
# 2. Login, Logout & 2FA
# =============================================================================

@method_decorator(
    rate_limit(key_func=get_client_ip, rate="10/h", method="POST", block=True),
    name="dispatch",
)
class CustomLoginView(LoginView):
    form_class = CustomLoginForm
    template_name = "accounts/login.html"

    def form_valid(self, form):
        user = form.get_user()
        if user and user.is_2fa_enabled:
            self.request.session["pre_2fa_user_id"] = str(user.pk)
            return redirect("two_factor_verify")
        return super().form_valid(form)

    def form_invalid(self, form):
        username = (form.data.get("username") or "").strip()
        password = form.data.get("password") or ""

        if username and password:
            candidate = User.objects.filter(
                Q(email__iexact=username) | Q(phone_number=username),
                is_active=False,
            ).first()
            
            # Nudge inactive users who entered the correct password
            if candidate and candidate.check_password(password):
                messages.warning(
                    self.request,
                    "Your account is not yet activated. Please click the verification link "
                    "in the email we sent, or request a new link below.",
                )
                self.request.session["pending_verification_email"] = candidate.email

        return super().form_invalid(form)


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy("login")


class TwoFactorVerifyView(View):
    template_name = "accounts/two_factor_verify.html"
    BACKEND = "accounts.backends.EmailOrPhoneBackend"

    def get(self, request):
        if not request.session.get("pre_2fa_user_id"):
            return redirect("login")
        form = TOTPTokenForm()
        return render(request, self.template_name, {"form": form, "show_recovery": True})

    def post(self, request):
        user_id = request.session.get("pre_2fa_user_id")
        if not user_id:
            return redirect("login")

        user = get_object_or_404(User, pk=user_id)
        token = request.POST.get("token")

        device = TOTPDevice.objects.filter(user=user, confirmed=True).first()
        if device and device.verify_token(token):
            login(request, user, backend=self.BACKEND)
            del request.session["pre_2fa_user_id"]
            return redirect(settings.LOGIN_REDIRECT_URL)

        recovery = RecoveryCode.objects.filter(user=user, code=token, is_used=False).first()
        if recovery:
            recovery.is_used = True
            recovery.save()
            login(request, user, backend=self.BACKEND)
            del request.session["pre_2fa_user_id"]
            messages.warning(request, "You used a recovery code. Please generate new ones in your profile.")
            return redirect(settings.LOGIN_REDIRECT_URL)

        messages.error(request, "Invalid code.")
        return render(request, self.template_name, {"form": TOTPTokenForm(), "show_recovery": True})


# =============================================================================
# 3. Profile & Client Team Management
# =============================================================================

class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile.html"


class ClientProfileEditView(LoginRequiredMixin, UpdateView):
    form_class = ClientProfileForm
    template_name = "accounts/client_profile_edit.html"
    success_url = reverse_lazy("profile")

    def get_object(self, queryset=None):
        return self.request.user

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["client_org"] = self.request.user.client_organization
        return kwargs

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def form_valid(self, form):
        messages.success(self.request, "Your profile has been updated.")
        return super().form_valid(form)


class ClientTeamListView(LoginRequiredMixin, ListView):
    model = User
    template_name = "accounts/client_team.html"
    context_object_name = "team_members"

    def get_queryset(self):
        client_org = self.request.user.client_organization
        if not client_org:
            return User.objects.none()
        return User.objects.filter(client_organization=client_org)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_invite"] = self.request.user.client_role == "admin"
        return ctx


@method_decorator(client_role_required(["admin"]), name="dispatch")
class ClientTeamInviteView(LoginRequiredMixin, View):
    def post(self, request):
        form = InviteTeamMemberForm(request.POST, client_org=request.user.client_organization)
        if form.is_valid():
            email = form.cleaned_data["email"]
            role = form.cleaned_data["role"]

            token = InvitationToken.objects.create(
                email=email,
                client_organization=request.user.client_organization,
                role=role,
            )
            invite_url = request.build_absolute_uri(reverse("accept_invite", args=[token.token]))

            send_mail(
                subject=f"Invitation to join {request.user.client_organization.name} on PriTech",
                message=f"Click the link to accept: {invite_url}\n\nThis link expires in 7 days.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            messages.success(request, f"Invitation sent to {email}.")
        else:
            messages.error(request, "Please correct the errors in the invitation form.")
        return redirect("client_team")


@method_decorator(client_role_required(["admin"]), name="dispatch")
class ClientTeamRemoveView(LoginRequiredMixin, View):
    def post(self, request, user_id):
        user_to_remove = get_object_or_404(
            User, pk=user_id, client_organization=request.user.client_organization
        )
        if user_to_remove == request.user:
            messages.error(request, "You cannot remove yourself.")
            return redirect("client_team")

        user_to_remove.delete()
        messages.success(request, f"Removed {user_to_remove.email} from your organisation.")
        return redirect("client_team")


class ClientAuditLogView(LoginRequiredMixin, ListView):
    model = UserAuditLog
    template_name = "accounts/client_audit_log.html"
    context_object_name = "logs"
    paginate_by = 50

    def get_queryset(self):
        client_org = self.request.user.client_organization
        if not client_org:
            return UserAuditLog.objects.none()
        user_ids = User.objects.filter(client_organization=client_org).values_list("id", flat=True)
        return UserAuditLog.objects.filter(user_id__in=user_ids).select_related("user").order_by("-timestamp")


def accept_invite(request, token):
    token_obj = get_object_or_404(InvitationToken, token=token)
    if not token_obj.is_valid():
        messages.error(request, "Invitation expired. Please ask for a new one.")
        return redirect("login")

    user = User.objects.filter(email=token_obj.email).first()

    if user:
        user.client_organization = token_obj.client_organization
        user.client_role = token_obj.role
        user.save(update_fields=["client_organization", "client_role"])
        messages.success(request, f"You've joined {token_obj.client_organization.name}. You can now log in.")
    else:
        temp_password = User.objects.make_random_password(length=12)
        user = User.objects.create_user(
            username=token_obj.email,
            email=token_obj.email,
            password=temp_password,
            first_name="",
            last_name="",
            user_type="client",
            client_organization=token_obj.client_organization,
            client_role=token_obj.role,
            is_active=True,
        )
        messages.success(
            request,
            f"You've joined {token_obj.client_organization.name}. Please use 'Forgot password' to set your password.",
        )

    token_obj.delete()
    return redirect("login")


# =============================================================================
# 4. Staff User Management (Admin Panel)
# =============================================================================

@method_decorator(staff_member_required, name="dispatch")
class UserListView(ListView):
    model = User
    template_name = "accounts/staff_user_list.html"
    context_object_name = "users"
    paginate_by = 50

    def get_queryset(self):
        qs = User.objects.all().prefetch_related("user_roles__role")
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
        user_type = self.request.GET.get("user_type")
        if user_type:
            qs = qs.filter(user_type=user_type)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["user_type_choices"] = User.USER_TYPE_CHOICES
        return ctx


@method_decorator(staff_member_required, name="dispatch")
class UserCreateView(CreateView):
    model = User
    form_class = StaffUserCreationForm
    template_name = "accounts/staff_user_form.html"
    success_url = reverse_lazy("user_list")

    def form_invalid(self, form):
        """Displays a top-level alert banner if the form is invalid."""
        messages.error(self.request, "Please correct the errors highlighted below.")
        return super().form_invalid(form)

    def form_valid(self, form):
        # The form hashes the password, generates the username and forces
        # user_type="staff" / is_staff=True inside save().
        user = form.save()
        self.object = user

        for role in form.cleaned_data.get("roles", []):
            UserRole.objects.get_or_create(user=user, role=role)

        messages.success(self.request, f"Staff user {user.email} created successfully.")
        return redirect(self.get_success_url())


@method_decorator(staff_member_required, name="dispatch")
class UserUpdateView(UpdateView):
    model = User
    form_class = StaffUserChangeForm
    template_name = "accounts/staff_user_form.html"
    success_url = reverse_lazy("user_list")

    def get_queryset(self):
        # Only staff accounts can be edited here (clients are managed elsewhere).
        return User.objects.filter(user_type="staff")

    def get_initial(self):
        initial = super().get_initial()
        initial["roles"] = UserRole.objects.filter(user=self.object).values_list("role_id", flat=True)
        return initial

    def form_invalid(self, form):
        """Displays a top-level alert banner if the form is invalid."""
        messages.error(self.request, "Please correct the errors highlighted below.")
        return super().form_invalid(form)

    def form_valid(self, form):
        # The form handles the optional password change and keeps the
        # account as user_type="staff" / is_staff=True.
        user = form.save()
        self.object = user

        # Sync Roles (Add new, Remove old)
        new_role_ids = set(form.cleaned_data["roles"].values_list("id", flat=True))
        current_role_ids = set(UserRole.objects.filter(user=user).values_list("role_id", flat=True))

        for role_id in new_role_ids - current_role_ids:
            UserRole.objects.get_or_create(user=user, role_id=role_id)
        for role_id in current_role_ids - new_role_ids:
            UserRole.objects.filter(user=user, role_id=role_id).delete()

        messages.success(self.request, f"User {user.email} updated successfully.")
        return redirect(self.get_success_url())


@method_decorator(staff_member_required, name="dispatch")
class UserDeleteView(DeleteView):
    model = User
    template_name = "accounts/staff_user_confirm_delete.html"
    success_url = reverse_lazy("user_list")

    def _block_privileged(self, request, user):
        """Prevent deletion of staff or superusers."""
        if user.is_superuser or user.is_staff:
            messages.error(request, "Cannot delete staff or superuser accounts. Demote the user first.")
            return redirect("user_list")
        return None

    def dispatch(self, request, *args, **kwargs):
        """Intercept request before routing to handler method."""
        user = self.get_object()
        blocked = self._block_privileged(request, user)
        if blocked:
            return blocked
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        """Second layer of defense before actual deletion."""
        user = self.get_object()
        blocked = self._block_privileged(request, user)
        if blocked:
            return blocked
        messages.success(request, f"User {user.email} deleted.")
        return super().delete(request, *args, **kwargs)


@method_decorator(staff_member_required, name="dispatch")
class StaffListView(LoginRequiredMixin, ListView):
    model = User
    template_name = "accounts/staff_list.html"
    context_object_name = "staff"

    def get_queryset(self):
        return User.objects.filter(user_type="staff").prefetch_related("user_roles__role")


# =============================================================================
# 5. Role, Permission & Analytics
# =============================================================================

@method_decorator(staff_member_required, name="dispatch")
class RoleListView(ListView):
    model = Role
    template_name = "accounts/role_list.html"
    context_object_name = "roles"


@method_decorator(staff_member_required, name="dispatch")
class RoleCreateView(CreateView):
    model = Role
    form_class = RoleForm
    template_name = "accounts/role_form.html"
    success_url = reverse_lazy("role_list")


@method_decorator(staff_member_required, name="dispatch")
class RoleUpdateView(UpdateView):
    model = Role
    form_class = RoleForm
    template_name = "accounts/role_form.html"
    success_url = reverse_lazy("role_list")


@method_decorator(staff_member_required, name="dispatch")
class RoleDeleteView(DeleteView):
    model = Role
    template_name = "accounts/role_confirm_delete.html"
    success_url = reverse_lazy("role_list")


@method_decorator(staff_member_required, name="dispatch")
class PermissionListView(ListView):
    model = Permission
    template_name = "accounts/permission_list.html"
    context_object_name = "permissions"


@method_decorator(staff_member_required, name="dispatch")
class PermissionCreateView(CreateView):
    model = Permission
    form_class = PermissionForm
    template_name = "accounts/permission_form.html"
    success_url = reverse_lazy("permission_list")


@method_decorator(staff_member_required, name="dispatch")
class PermissionUpdateView(UpdateView):
    model = Permission
    form_class = PermissionForm
    template_name = "accounts/permission_form.html"
    success_url = reverse_lazy("permission_list")


@method_decorator(staff_member_required, name="dispatch")
class PermissionDeleteView(DeleteView):
    model = Permission
    template_name = "accounts/permission_confirm_delete.html"
    success_url = reverse_lazy("permission_list")


@method_decorator(staff_member_required, name="dispatch")
class AnalyticsView(TemplateView):
    template_name = "accounts/analytics.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        last_30_days = now - timedelta(days=30)

        # Login Stats
        login_stats = LoginEvent.objects.filter(timestamp__gte=last_30_days).values("event_type").annotate(count=Count("id"))
        ctx["login_stats"] = {item["event_type"]: item["count"] for item in login_stats}

        # Daily Logins
        ctx["daily_logins"] = list(
            LoginEvent.objects.filter(event_type="success", timestamp__gte=last_30_days)
            .annotate(day=TruncDay("timestamp")).values("day").annotate(count=Count("id")).order_by("day")
        )

        # Monthly Growth
        ctx["monthly_growth"] = list(
            User.objects.annotate(month=TruncMonth("date_joined")).values("month").annotate(count=Count("id")).order_by("month")
        )

        # Active Sessions
        active_threshold = now - timedelta(minutes=30)
        ctx["active_users_now"] = UserSession.objects.filter(last_activity__gte=active_threshold, is_active=True).values("user").distinct().count()

        # Device Stats
        ctx["device_stats"] = UserSession.objects.filter(login_time__gte=last_30_days).values("device").annotate(count=Count("id")).order_by("-count")

        # Cumulative Growth
        users_by_day = User.objects.annotate(day=TruncDay("date_joined")).values("day").annotate(count=Count("id")).order_by("day")
        cumulative = []
        total = 0
        for item in users_by_day:
            total += item["count"]
            cumulative.append({"day": item["day"], "total": total})
        ctx["cumulative_users"] = cumulative
        ctx["total_users"] = User.objects.count()
        
        return ctx

    def render_to_response(self, context, **response_kwargs):
        # Partial render for HTMX polling
        if self.request.headers.get("HX-Request"):
            return render(self.request, "accounts/analytics_partial.html", context)
        return super().render_to_response(context, **response_kwargs)


@login_required
def recovery_codes_view(request):
    user = request.user
    codes = RecoveryCode.objects.filter(user=user, is_used=False)

    if request.method == "POST":
        RecoveryCode.objects.filter(user=user).delete()
        RecoveryCode.generate_for_user(user)
        messages.success(request, "New recovery codes generated.")
        return redirect("recovery_codes")

    return render(request, "accounts/recovery_codes.html", {"codes": codes})