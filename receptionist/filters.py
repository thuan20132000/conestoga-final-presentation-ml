import django_filters
from django.db.models import Q
from datetime import datetime, timedelta
from .models import (
    CallSession, ConversationMessage, 
    Intent, SystemLog
)
from business.models import Business


class BusinessFilter(django_filters.FilterSet):
    """Filter for Business model."""
    
    name = django_filters.CharFilter(lookup_expr='icontains')
    phone_number = django_filters.CharFilter(lookup_expr='icontains')
    timezone = django_filters.CharFilter(lookup_expr='icontains')
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    class Meta:
        model = Business
        fields = ['name', 'phone_number', 'timezone', 'created_after', 'created_before']


class CallSessionFilter(django_filters.FilterSet):
    """Filter for CallSession model."""
    
    business = django_filters.ModelChoiceFilter(queryset=Business.objects.all(), lookup_expr='exact')
    business_name = django_filters.CharFilter(field_name='business__name', lookup_expr='icontains')
    direction = django_filters.ChoiceFilter(choices=CallSession.CALL_DIRECTION_CHOICES)
    status = django_filters.ChoiceFilter(choices=CallSession.STATUS_CHOICES)
    caller_number = django_filters.CharFilter(lookup_expr='icontains')
    call_sid = django_filters.CharFilter(lookup_expr='icontains')
    
    # Date filters
    started_after = django_filters.DateTimeFilter(field_name='started_at', lookup_expr='gte')
    started_before = django_filters.DateTimeFilter(field_name='started_at', lookup_expr='lte')
    ended_after = django_filters.DateTimeFilter(field_name='ended_at', lookup_expr='gte')
    ended_before = django_filters.DateTimeFilter(field_name='ended_at', lookup_expr='lte')
    
    # Duration filters
    min_duration = django_filters.NumberFilter(field_name='duration_seconds', lookup_expr='gte')
    max_duration = django_filters.NumberFilter(field_name='duration_seconds', lookup_expr='lte')
    
    # Today's calls
    today = django_filters.BooleanFilter(method='filter_today')
    
    # This week's calls
    this_week = django_filters.BooleanFilter(method='filter_this_week')
    
    # This month's calls
    this_month = django_filters.BooleanFilter(method='filter_this_month')
    
    class Meta:
        model = CallSession
        fields = [
            'business', 'business_name', 'direction', 'status', 'caller_number',
            'call_sid', 'started_after', 'started_before', 'ended_after', 
            'ended_before', 'min_duration', 'max_duration', 'today', 
            'this_week', 'this_month'
        ]
    
    def filter_today(self, queryset, name, value):
        """Filter calls from today."""
        if value:
            today = datetime.now().date()
            return queryset.filter(started_at__date=today)
        return queryset
    
    def filter_this_week(self, queryset, name, value):
        """Filter calls from this week."""
        if value:
            today = datetime.now().date()
            week_start = today - timedelta(days=today.weekday())
            return queryset.filter(started_at__date__gte=week_start)
        return queryset
    
    def filter_this_month(self, queryset, name, value):
        """Filter calls from this month."""
        if value:
            today = datetime.now().date()
            month_start = today.replace(day=1)
            return queryset.filter(started_at__date__gte=month_start)
        return queryset


class ConversationMessageFilter(django_filters.FilterSet):
    """Filter for ConversationMessage model."""
    
    call = django_filters.ModelChoiceFilter(queryset=CallSession.objects.all(), lookup_expr='exact')
    call_sid = django_filters.CharFilter(field_name='call__call_sid', lookup_expr='icontains')
    role = django_filters.ChoiceFilter(choices=ConversationMessage.ROLE_CHOICES)
    content = django_filters.CharFilter(lookup_expr='icontains')
    
    # Date filters
    timestamp_after = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
    timestamp_before = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')
    
    # Confidence filters
    min_confidence = django_filters.NumberFilter(field_name='confidence_score', lookup_expr='gte')
    max_confidence = django_filters.NumberFilter(field_name='confidence_score', lookup_expr='lte')
    
    class Meta:
        model = ConversationMessage
        fields = [
            'call', 'call_sid', 'role', 'content', 'timestamp_after', 
            'timestamp_before', 'min_confidence', 'max_confidence'
        ]


class IntentFilter(django_filters.FilterSet):
    """Filter for Intent model."""
    
    call = django_filters.ModelChoiceFilter(queryset=CallSession.objects.all(), lookup_expr='exact')
    call_sid = django_filters.CharFilter(field_name='call__call_sid', lookup_expr='icontains')
    name = django_filters.CharFilter(lookup_expr='icontains')
    
    # Confidence filters
    min_confidence = django_filters.NumberFilter(field_name='confidence', lookup_expr='gte')
    max_confidence = django_filters.NumberFilter(field_name='confidence', lookup_expr='lte')
    
    # Date filters
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    # High confidence intents
    high_confidence = django_filters.BooleanFilter(method='filter_high_confidence')
    
    class Meta:
        model = Intent
        fields = [
            'call', 'call_sid', 'name', 'min_confidence', 'max_confidence',
            'created_after', 'created_before', 'high_confidence'
        ]
    
    def filter_high_confidence(self, queryset, name, value):
        """Filter intents with high confidence (>0.8)."""
        if value:
            return queryset.filter(confidence__gte=0.8)
        return queryset


class SystemLogFilter(django_filters.FilterSet):
    """Filter for SystemLog model."""
    
    call = django_filters.ModelChoiceFilter(queryset=CallSession.objects.all(), lookup_expr='exact')
    call_sid = django_filters.CharFilter(field_name='call__call_sid', lookup_expr='icontains')
    level = django_filters.ChoiceFilter(choices=[("info", "Info"), ("warning", "Warning"), ("error", "Error")])
    message = django_filters.CharFilter(lookup_expr='icontains')
    
    # Date filters
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    # Today's logs
    today = django_filters.BooleanFilter(method='filter_today')
    
    # Error logs only
    errors_only = django_filters.BooleanFilter(method='filter_errors_only')
    
    class Meta:
        model = SystemLog
        fields = [
            'call', 'call_sid', 'level', 'message', 'created_after', 
            'created_before', 'today', 'errors_only'
        ]
    
    def filter_today(self, queryset, name, value):
        """Filter logs from today."""
        if value:
            today = datetime.now().date()
            return queryset.filter(created_at__date=today)
        return queryset
    
    def filter_errors_only(self, queryset, name, value):
        """Filter only error level logs."""
        if value:
            return queryset.filter(level='error')
        return queryset
