# accounts/admin.py
from unfold.admin import ModelAdmin
from django.contrib import admin
from django.contrib.admin import site as admin_site
from allauth.socialaccount.models import SocialApp, SocialAccount, SocialToken
from .models import User, Role, Permission, UserRole, RolePermission, UserAuditLog, EmailVerificationToken, InvitationToken

# ========== Unregister allauth default admins (to replace with Unfold) ==========
try:
    admin_site.unregister(SocialApp)
except admin.sites.NotRegistered:
    pass
try:
    admin_site.unregister(SocialAccount)
except admin.sites.NotRegistered:
    pass
try:
    admin_site.unregister(SocialToken)
except admin.sites.NotRegistered:
    pass

# ========== User admin (inherit only from Unfold ModelAdmin) ==========
@admin.register(User)
class UserAdmin(ModelAdmin):
    list_display = ('email', 'get_full_name', 'user_type', 'client_role', 'is_active', 'last_login')
    list_filter = ('user_type', 'client_role', 'is_active')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    readonly_fields = ('last_login', 'date_joined', 'last_login_ip')
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone_number', 'physical_address')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Profile', {'fields': ('user_type', 'client_role', 'national_id', 'last_login_ip')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'first_name', 'last_name', 'password1', 'password2', 'user_type', 'client_role'),
        }),
    )
    ordering = ('email',)

# ========== Other accounts models ==========
@admin.register(Role)
class RoleAdmin(ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')

@admin.register(Permission)
class PermissionAdmin(ModelAdmin):
    list_display = ('code', 'description')
    search_fields = ('code',)

@admin.register(UserRole)
class UserRoleAdmin(ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__email',)

@admin.register(RolePermission)
class RolePermissionAdmin(ModelAdmin):
    list_display = ('role', 'permission')
    list_filter = ('role',)
    search_fields = ('role__name', 'permission__code')

@admin.register(UserAuditLog)
class UserAuditLogAdmin(ModelAdmin):
    list_display = ('user', 'action', 'ip_address', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('user__email', 'action')
    readonly_fields = ('user', 'action', 'ip_address', 'user_agent', 'timestamp')

@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(ModelAdmin):
    list_display = ('user', 'token', 'created_at', 'is_valid')
    list_filter = ('created_at',)
    readonly_fields = ('user', 'token', 'created_at')
    def is_valid(self, obj):
        return obj.is_valid()
    is_valid.boolean = True

@admin.register(InvitationToken)
class InvitationTokenAdmin(ModelAdmin):
    list_display = ('email', 'client_organization', 'role', 'created_at', 'is_valid')
    list_filter = ('role', 'created_at')
    search_fields = ('email', 'client_organization__name')
    readonly_fields = ('email', 'token', 'client_organization', 'role', 'created_at')
    def is_valid(self, obj):
        return obj.is_valid()
    is_valid.boolean = True

# ========== Allauth social models (registered with Unfold) ==========
@admin.register(SocialApp)
class SocialAppAdmin(ModelAdmin):
    list_display = ('name', 'provider', 'client_id')
    search_fields = ('name', 'provider')
    list_filter = ('provider',)

@admin.register(SocialAccount)
class SocialAccountAdmin(ModelAdmin):
    list_display = ('user', 'provider', 'uid')
    search_fields = ('user__email', 'provider', 'uid')
    raw_id_fields = ('user',)

@admin.register(SocialToken)
class SocialTokenAdmin(ModelAdmin):
    list_display = ('app', 'account', 'expires_at')
    raw_id_fields = ('app', 'account')