from django.contrib import admin
from .models import AppointmentService, Appointment
from simple_history.admin import SimpleHistoryAdmin

class AppointmentServiceInlineAdmin(admin.TabularInline):
    model = AppointmentService
    extra = 1
    fk_name = 'appointment'
    verbose_name = 'Service'
    verbose_name_plural = 'Services'
    fields = ['service', 'staff', 'is_staff_request', 'custom_price', 'custom_duration', 'start_at', 'end_at', 'is_active']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Appointment)    
class AppointmentAdmin(SimpleHistoryAdmin):
    list_display = [
        'client', 
        'business', 
        'appointment_date', 
        'status', 
        'booking_source', 
        'created_at', 
        'updated_at',
        'is_active',
    ]
    list_filter = ['status', 'business', 'booking_source']
    list_per_page = 20
    list_editable = ['status']
    list_display_links = ['client', 'business', 'appointment_date']
    list_select_related = ['client', 'business']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = [
        (None, {'fields': ['client', 'business', 'appointment_date', 'status', 'booked_by', 'booking_source', 'created_at', 'updated_at', 'is_active', 'metadata']}),
    ]
    inlines = [AppointmentServiceInlineAdmin]
    
@admin.register(AppointmentService)
class AppointmentServiceAdmin(SimpleHistoryAdmin):
    list_display = [
        'appointment', 
        'service', 
        'staff', 
        'is_staff_request', 
        'custom_price', 
        'custom_duration', 
        'start_at', 
        'end_at', 'created_at', 'updated_at']
    list_filter = ['appointment__business']
    list_per_page = 50
    ordering = ['-created_at']
    
