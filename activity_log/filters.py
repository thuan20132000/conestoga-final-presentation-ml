import django_filters
from .models import ActivityLog


class ActivityLogFilter(django_filters.FilterSet):
    business_id = django_filters.UUIDFilter(field_name='business_id')
    action = django_filters.CharFilter(field_name='action')
    actor_id = django_filters.NumberFilter(field_name='actor_id')
    date_from = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    date_to = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    target_content_type = django_filters.NumberFilter(field_name='target_content_type_id')
    target_object_id = django_filters.CharFilter(field_name='target_object_id')

    class Meta:
        model = ActivityLog
        fields = [
            'business_id', 'action', 'actor_id',
            'date_from', 'date_to',
            'target_content_type', 'target_object_id',
        ]
