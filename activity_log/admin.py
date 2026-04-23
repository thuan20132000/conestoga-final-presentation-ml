from django.contrib import admin
from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['actor_name', 'action', 'description', 'business', 'created_at']
    list_filter = ['action', 'business', 'created_at']
    search_fields = ['actor_name', 'description', 'target_repr']
    readonly_fields = [
        'actor', 'actor_name', 'action', 'description',
        'target_content_type', 'target_object_id', 'target_repr',
        'changes', 'metadata', 'ip_address', 'business', 'created_at',
    ]
    list_per_page = 50
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
