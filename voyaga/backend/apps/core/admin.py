from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, OTPCode, AuditLog


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['email', 'username', 'role', 'is_verified', 'wallet_balance', 'created_at']
    list_filter = ['role', 'is_verified']
    fieldsets = UserAdmin.fieldsets + (
        ('Voyaga', {'fields': ('role', 'avatar', 'bio', 'phone', 'wallet_balance', 'is_verified')}),
    )


@admin.register(OTPCode)
class OTPAdmin(admin.ModelAdmin):
    list_display = ['user', 'code', 'is_used', 'created_at']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'ip_address', 'created_at']