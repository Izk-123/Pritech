# accounts/models.py
import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.conf import settings


class User(AbstractUser):
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
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return f"{self.get_full_name() or self.email} ({self.user_type})"

    def has_role(self, role_code):
        return self.user_roles.filter(role__code=role_code).exists()

    def has_perm_code(self, permission_code):
        from .models import RolePermission
        return RolePermission.objects.filter(
            role__user_roles__user=self,
            permission__code=permission_code
        ).exists()

    @property
    def primary_role(self):
        ur = self.user_roles.select_related('role').first()
        return ur.role if ur else None


class Role(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Permission(models.Model):
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField()

    def __str__(self):
        return self.code


class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_roles')

    class Meta:
        unique_together = ('user', 'role')


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='role_permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('role', 'permission')


class UserAuditLog(models.Model):
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
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='verification_token')
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return (timezone.now() - self.created_at).days < 1  # 24 hours expiry

    def __str__(self):
        return f"Token for {self.user.email}"


class InvitationToken(models.Model):
    email = models.EmailField()
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    client_organization = models.ForeignKey('clients.ClientOrganization', on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=User.CLIENT_ROLE_CHOICES, default='viewer')
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return (timezone.now() - self.created_at).days < 7  # valid for 7 days

    def __str__(self):
        return f"Invitation for {self.email} to {self.client_organization.name}"