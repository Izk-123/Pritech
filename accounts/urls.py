# accounts/urls.py
"""
URL configuration for accounts app.

── NEW ──────────────────────────────────────────────────────────────────────
* /check-email/          → CheckYourEmailView  (post-registration landing)
* /resend-verification/  → ResendVerificationView (POST)
"""

from django.contrib.auth import views as auth_views
from django.urls import path

from .views import (
    AnalyticsView,
    CheckYourEmailView,          # NEW
    ClientAuditLogView,
    ClientProfileEditView,
    ClientRegisterView,
    ClientTeamInviteView,
    ClientTeamListView,
    ClientTeamRemoveView,
    CustomLoginView,
    CustomLogoutView,
    PermissionCreateView,
    PermissionDeleteView,
    PermissionListView,
    PermissionUpdateView,
    ProfileView,
    ResendVerificationView,      # NEW
    RoleCreateView,
    RoleDeleteView,
    RoleListView,
    RoleUpdateView,
    StaffListView,               # legacy
    TwoFactorVerifyView,
    UserCreateView,
    UserDeleteView,
    UserListView,
    UserUpdateView,
    accept_invite,
    recovery_codes_view,
    verify_email,
)
from .views_2fa import two_factor_disable, two_factor_setup

urlpatterns = [
    # ----- Registration & login ---------------------------------------------
    path("register/", ClientRegisterView.as_view(), name="register"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", CustomLogoutView.as_view(), name="logout"),

    # ----- Email verification -----------------------------------------------
    # NEW: the two routes below are required by the updated verification flow.
    path(
        "check-email/",
        CheckYourEmailView.as_view(),
        name="check_your_email",
    ),
    path(
        "resend-verification/",
        ResendVerificationView.as_view(),
        name="resend_verification",
    ),
    path(
        "verify-email/<uuid:token>/",
        verify_email,
        name="verify_email",
    ),

    # ----- Password reset (Django built-in) ---------------------------------
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset.html",
            email_template_name="accounts/password_reset_email.html",
            subject_template_name="accounts/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),

    # ----- Staff listing (legacy) -------------------------------------------
    path("staff/", StaffListView.as_view(), name="staff_list"),

    # ----- Profile & client self-service ------------------------------------
    path("profile/", ProfileView.as_view(), name="profile"),
    path("team/", ClientTeamListView.as_view(), name="client_team"),
    path(
        "team/invite/",
        ClientTeamInviteView.as_view(),
        name="client_team_invite",
    ),
    path(
        "team/remove/<int:user_id>/",
        ClientTeamRemoveView.as_view(),
        name="client_team_remove",
    ),
    path(
        "profile/edit/",
        ClientProfileEditView.as_view(),
        name="client_profile_edit",
    ),
    path(
        "audit/",
        ClientAuditLogView.as_view(),
        name="client_audit_log",
    ),

    # ----- Invitation -------------------------------------------------------
    path(
        "accept-invite/<uuid:token>/",
        accept_invite,
        name="accept_invite",
    ),

    # ----- 2FA --------------------------------------------------------------
    path("2fa/setup/", two_factor_setup, name="two_factor_setup"),
    path("2fa/disable/", two_factor_disable, name="two_factor_disable"),
    path(
        "2fa/verify/",
        TwoFactorVerifyView.as_view(),
        name="two_factor_verify",
    ),

    # ----- Recovery codes ---------------------------------------------------
    path(
        "recovery-codes/",
        recovery_codes_view,
        name="recovery_codes",
    ),

    # ----- Staff user management -------------------------------------------
    path("staff/users/", UserListView.as_view(), name="user_list"),
    path(
        "staff/users/create/",
        UserCreateView.as_view(),
        name="user_create",
    ),
    path(
        "staff/users/<uuid:pk>/edit/",
        UserUpdateView.as_view(),
        name="user_update",
    ),
    path(
        "staff/users/<uuid:pk>/delete/",
        UserDeleteView.as_view(),
        name="user_delete",
    ),

    # ----- Role management --------------------------------------------------
    path("staff/roles/", RoleListView.as_view(), name="role_list"),
    path(
        "staff/roles/create/",
        RoleCreateView.as_view(),
        name="role_create",
    ),
    path(
        "staff/roles/<int:pk>/edit/",
        RoleUpdateView.as_view(),
        name="role_update",
    ),
    path(
        "staff/roles/<int:pk>/delete/",
        RoleDeleteView.as_view(),
        name="role_delete",
    ),

    # ----- Permission management -------------------------------------------
    path(
        "staff/permissions/",
        PermissionListView.as_view(),
        name="permission_list",
    ),
    path(
        "staff/permissions/create/",
        PermissionCreateView.as_view(),
        name="permission_create",
    ),
    path(
        "staff/permissions/<int:pk>/edit/",
        PermissionUpdateView.as_view(),
        name="permission_update",
    ),
    path(
        "staff/permissions/<int:pk>/delete/",
        PermissionDeleteView.as_view(),
        name="permission_delete",
    ),

    # ----- Analytics --------------------------------------------------------
    path(
        "staff/analytics/",
        AnalyticsView.as_view(),
        name="analytics",
    ),
]