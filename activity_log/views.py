from rest_framework import filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from main.viewsets import BaseModelViewSet
from .models import ActivityLog
from .serializers import ActivityLogSerializer
from .filters import ActivityLogFilter


class ActivityLogViewSet(BaseModelViewSet):
    queryset = ActivityLog.objects.select_related(
        'actor', 'target_content_type', 'business'
    ).all()
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ActivityLogFilter
    search_fields = ['description', 'actor_name', 'target_repr']
    ordering_fields = ['created_at', 'action']
    ordering = ['-created_at']
    http_method_names = ['get', 'head', 'options']
