# accounts/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from .views_2fa import two_factor_disable, two_factor_setup
from .views import (
    ClientRegisterView,
    CustomLoginView,
    CustomLogoutView,
    StaffListView,
    ProfileView,
    ClientTeamListView,
    ClientTeamInviteView,
    ClientTeamRemoveView,
    ClientProfileEditView,
    ClientAuditLogView,
    TwoFactorVerifyView,
    accept_invite,
    verify_email,
)

urlpatterns = [
    # Registration & login
    path('register/', ClientRegisterView.as_view(), name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    
    # Email verification
    path('verify-email/<uuid:token>/', verify_email, name='verify_email'),
    
    # Password reset (Django built-in)
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='accounts/password_reset.html',
             email_template_name='accounts/password_reset_email.html',
             subject_template_name='accounts/password_reset_subject.txt'
         ),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='accounts/password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'),
         name='password_reset_complete'),
    
    # Staff listing (internal)
    path('staff/', StaffListView.as_view(), name='staff_list'),
    
    # Profile (read-only)
    path('profile/', ProfileView.as_view(), name='profile'),
    
    # Client self-service
    path('team/', ClientTeamListView.as_view(), name='client_team'),
    path('team/invite/', ClientTeamInviteView.as_view(), name='client_team_invite'),
    path('team/remove/<int:user_id>/', ClientTeamRemoveView.as_view(), name='client_team_remove'),
    path('profile/edit/', ClientProfileEditView.as_view(), name='client_profile_edit'),
    path('audit/', ClientAuditLogView.as_view(), name='client_audit_log'),
    
    path('accept-invite/<uuid:token>/', accept_invite, name='accept_invite'),
    path('2fa/setup/', two_factor_setup, name='two_factor_setup'),
    path('2fa/disable/', two_factor_disable, name='two_factor_disable'),
    path('2fa/verify/', TwoFactorVerifyView.as_view(), name='two_factor_verify')
]