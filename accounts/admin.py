from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Role, Permission, UserRole, RolePermission, UserAuditLog


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'get_full_name', 'user_type', 'is_active', 'date_joined')
    list_filter = ('user_type', 'is_active')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Profile', {'fields': ('user_type', 'phone_number', 'national_id', 'physical_address', 'last_login_ip')}),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')


admin.site.register(Permission)
admin.site.register(UserRole)
admin.site.register(RolePermission)
admin.site.register(UserAuditLog)
