from django.contrib import admin
from .models import ServiceCategory, Service
from simple_history.admin import SimpleHistoryAdmin


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(SimpleHistoryAdmin):
    list_display = ['name', 'business', 'sort_order', 'is_active', 'created_at']
    list_filter = ['business', 'is_active', 'created_at']
    search_fields = ['name', 'description', 'business__name']
    ordering = ['business__name', 'sort_order', 'name']


@admin.register(Service)
class ServiceAdmin(SimpleHistoryAdmin):
    list_display = ['name', 'business', 'category', 'price', 'duration_minutes', 'is_active']
    list_filter = ['business', 'category', 'is_active', 'requires_staff', 'created_at']
    search_fields = ['name', 'description', 'business__name', 'category__name']
    ordering = ['business__name', 'category__sort_order', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('business', 'category', 'name', 'description', 'is_online_booking','color_code','icon','image')
        }),
        ('Service Details', {
            'fields': ('duration_minutes', 'price', 'max_capacity', 'requires_staff', 'sort_order')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
