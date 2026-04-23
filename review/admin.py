from django.contrib import admin
from .models import Review
from simple_history.admin import SimpleHistoryAdmin


@admin.register(Review)
class ReviewAdmin(SimpleHistoryAdmin):
    list_display = [
        'id',
        'appointment',
        'rating',
        'is_visible',
        'is_verified',
        'reviewed_at',
        'created_at'
    ]
    list_filter = [
        'rating',
        'is_visible',
        'is_verified',
        'is_active',
        'reviewed_at',
        'created_at'
    ]
    list_per_page = 20
    list_editable = ['is_visible', 'is_verified']
    list_display_links = ['appointment']
    list_select_related = ['appointment', 'appointment__business']
    readonly_fields = ['reviewed_at', 'created_at', 'updated_at']
    search_fields = [
        'appointment__id',
        'comment'
    ]
    fieldsets = [
        (
            'Review Information',
            {
                'fields': [
                    'appointment',
                    'rating',
                    'comment',
                    'is_visible',
                    'is_verified',
                    'reviewed_at'
                ]
            }
        ),
        (
            'Metadata',
            {
                'fields': [
                    'is_active',
                    'metadata',
                    'created_at',
                    'updated_at'
                ]
            }
        ),
    ]
