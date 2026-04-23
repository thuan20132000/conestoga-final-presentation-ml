from django.contrib import admin
from .models import StaffTurn, Turn, TurnService, StaffTurnServiceAssignment
from business.models import Business
from service.models import Service


@admin.register(StaffTurn)
class StaffTurnAdmin(admin.ModelAdmin):
    list_filter = ['business', 'date', 'is_available']
    ordering = ['date', 'position']


@admin.register(Turn)
class TurnAdmin(admin.ModelAdmin):
    list_filter = ['status', 'staff_turn__date', 'is_client_request']
    ordering = ['-created_at']


@admin.register(TurnService)
class TurnServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'business', 'is_active']
    filter_horizontal = ['services']
    ordering = ['name']
    search_fields = ['name', 'business__name']
    list_filter = ['is_active']


@admin.register(StaffTurnServiceAssignment)
class StaffTurnServiceAssignmentAdmin(admin.ModelAdmin):
    list_display = ['staff', 'turn_service']
    list_filter = ['turn_service__business', 'turn_service']
    ordering = ['turn_service', 'staff']
