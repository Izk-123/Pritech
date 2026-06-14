# accounts/models.py
"""
Accounts App – Core Models
---------------------------
- User (custom user model with UUID, email as USERNAME_FIELD)
- Role, Permission, UserRole, RolePermission (RBAC)
- UserProfile (extra profile data)
- UserSession (active session tracking)
- LoginEvent (analytics)
- RecoveryCode (2FA backup codes)
- UserAuditLog, EmailVerificationToken, InvitationToken (existing)
"""

import uuid
import secrets
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.conf import settings


# ============================================================================
# Core User Model
# ============================================================================

class User(AbstractUser):
    """
    Custom User model using email as the unique identifier.
    Adds fields for client organisation, 2FA, and client roles.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    USER_TYPE_CHOICES = (('client', 'Client'), ('staff', 'Staff'))
    CLIENT_ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('viewer', 'Viewer'),
        ('billing', 'Billing'),
    ]

    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='client')
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    national_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    physical_address = models.TextField(blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    client_role = models.CharField(
        max_length=20,
        choices=CLIENT_ROLE_CHOICES,
        default='viewer',
        blank=True,
        help_text="Role within the client organization (only for client users)"
    )
    is_2fa_enabled = models.BooleanField(default=False)

    # ---- FIX: link to ClientOrganization (many users per organisation) ----
    client_organization = models.ForeignKey(
        'clients.ClientOrganization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        help_text="The organisation this user belongs to (client users only)"
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        ordering = ['email']

    def __str__(self):
        return f"{self.get_full_name() or self.email} ({self.user_type})"

    def has_role(self, role_code: str) -> bool:
        """Check if user has a specific role by code."""
        return self.user_roles.filter(role__code=role_code).exists()

    def has_perm_code(self, permission_code: str) -> bool:
        """Check if user has a specific permission code via roles."""
        from .models import RolePermission
        return RolePermission.objects.filter(
            role__user_roles__user=self,
            permission__code=permission_code
        ).exists()

    @property
    def primary_role(self):
        """Return the first assigned role (convenience property)."""
        ur = self.user_roles.select_related('role').first()
        return ur.role if ur else None


# ============================================================================
# User Profile (extra fields)
# ============================================================================

class UserProfile(models.Model):
    """
    Additional user information: photo, gender, date of birth, bio.
    One-to-one with User.
    """
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    bio = models.TextField(blank=True)

    def __str__(self):
        return f"Profile of {self.user.email}"


# ============================================================================
# Session Tracking (Real‑time presence)
# ============================================================================

class UserSession(models.Model):
    """
    Tracks active user sessions for real‑time presence and analytics.
    Updated on login, logout, and periodic activity.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    device = models.CharField(max_length=100, blank=True, help_text="Parsed device type (Desktop/Mobile/Tablet)")
    login_time = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-login_time']

    def __str__(self):
        return f"{self.user.email} - {self.ip_address} ({self.login_time.strftime('%Y-%m-%d %H:%M')})"


# ============================================================================
# Login Analytics
# ============================================================================

class LoginEvent(models.Model):
    """
    Records every login attempt (success/failure/logout) for analytics.
    """
    EVENT_TYPES = (
        ('success', 'Successful Login'),
        ('failed', 'Failed Login'),
        ('logout', 'Logout'),
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField(max_length=10, choices=EVENT_TYPES)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=255, blank=True, help_text="Failure reason, if any")

    def __str__(self):
        return f"{self.event_type} - {self.user} at {self.timestamp}"


# ============================================================================
# 2FA Recovery Codes
# ============================================================================

class RecoveryCode(models.Model):
    """
    One‑time backup codes for two‑factor authentication.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recovery_codes')
    code = models.CharField(max_length=10, unique=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Recovery code for {self.user.email}"

    @classmethod
    def generate_for_user(cls, user, num_codes=10):
        """Generate a set of recovery codes for a user."""
        codes = []
        for _ in range(num_codes):
            code = secrets.token_hex(3).upper()   # 6 hex characters
            codes.append(cls(user=user, code=code))
        cls.objects.bulk_create(codes)
        return codes


# ============================================================================
# RBAC Models (unchanged from original, but kept for completeness)
# ============================================================================

class Role(models.Model):
    """User role (e.g., ADMIN, TECHNICIAN, FINANCE)."""
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Permission(models.Model):
    """Fine‑grained permission (e.g., view_invoice, create_ticket)."""
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField()

    def __str__(self):
        return self.code


class UserRole(models.Model):
    """Many‑to‑many between User and Role."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_roles')

    class Meta:
        unique_together = ('user', 'role')


class RolePermission(models.Model):
    """Many‑to‑many between Role and Permission."""
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='role_permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('role', 'permission')


# ============================================================================
# Audit & Invitation Models (unchanged)
# ============================================================================

class UserAuditLog(models.Model):
    """Audit trail for user actions (login, logout, critical changes)."""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user} - {self.action}"


class EmailVerificationToken(models.Model):
    """Token for email verification (24h expiry)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='verification_token')
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return (timezone.now() - self.created_at).days < 1

    def __str__(self):
        return f"Token for {self.user.email}"


class InvitationToken(models.Model):
    """Invitation token for adding team members (7 days expiry)."""
    email = models.EmailField()
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    client_organization = models.ForeignKey('clients.ClientOrganization', on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=User.CLIENT_ROLE_CHOICES, default='viewer')
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return (timezone.now() - self.created_at).days < 7

    def __str__(self):
        return f"Invitation for {self.email} to {self.client_organization.name}"