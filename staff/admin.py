from django.contrib import admin
from .models import Staff, StaffService, StaffWorkingHours, StaffOffDay, TimeEntry, StaffWorkingHoursOverride
from django.contrib.auth.admin import UserAdmin

class StaffServiceInline(admin.TabularInline):
    model = StaffService
    extra = 0
    fields = ['service', 'is_primary']

class StaffWorkingHoursInline(admin.TabularInline):
    model = StaffWorkingHours
    extra = 0
    fields = ['day_of_week', 'start_time', 'end_time', 'is_working']

class StaffOffDayInline(admin.TabularInline):
    model = StaffOffDay
    extra = 0
    fields = ['start_date', 'end_date', 'reason']

class StaffWorkingHoursOverrideInline(admin.TabularInline):
    model = StaffWorkingHoursOverride
    extra = 0
    fields = ['date', 'start_time', 'end_time', 'is_working', 'reason']

@admin.register(Staff)
class StaffAdmin(UserAdmin):
    """Admin interface for Staff model"""

    list_display = [
        "username",
        "first_name",
        "role",
        "is_active",
        "hire_date",
        "last_login",
        "business",
    ]
    list_filter = [
        "business",
    ]
    search_fields = ["username", "first_name", "last_name", "email", "business", "role"]
    ordering = ["role", "username"]

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": (
            "first_name", "last_name", "email", "phone", "photo", "bio", "staff_code", "commission_rate")}),
        ("Business Info", {"fields": ("role", "business", "hire_date", "is_online_booking_allowed", "is_payment_processing_allowed")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
        ("Soft delete", {"fields": ("is_deleted", "deleted_at")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "password1",
                    "password2",
                    "first_name",
                    "last_name",
                    "role",
                    "business",
                    "hire_date",
                    "bio",
                    "staff_code",
                    "photo",
                ),
            },
        ),
    )

    readonly_fields = ["date_joined", "last_login"]
    inlines = [StaffWorkingHoursInline, StaffOffDayInline, StaffWorkingHoursOverrideInline]

@admin.register(StaffService)
class StaffServiceAdmin(admin.ModelAdmin):
    list_display = ['staff', 'service', 'is_primary', 'created_at']
    list_filter = ['is_primary', 'created_at', 'staff__business']
    search_fields = ['staff__username', 'staff__business']
    ordering = ['staff__business__name', 'staff__username', 'service', 'id']
    

@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ['staff', 'clock_in', 'clock_out', 'total_minutes', 'overtime_minutes', 'status', 'created_at', 'updated_at']
    list_filter = ['status', 'created_at', 'staff__business']
    search_fields = ['staff__username', 'staff__business']
    ordering = ['staff__business__name', 'staff__username', 'clock_in', 'id']
    
@admin.register(StaffWorkingHoursOverride)
class StaffWorkingHoursOverrideAdmin(admin.ModelAdmin):
    list_display = ['staff', 'date', 'start_time', 'end_time', 'is_working', 'reason']
    list_filter = ['is_working', 'date', 'staff__business']
    search_fields = ['staff__username', 'staff__business']
    ordering = ['staff__business__name', 'staff__username', 'date', 'id']