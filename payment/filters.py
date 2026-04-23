import django_filters
from django.db.models import Q
from datetime import datetime, timedelta
from .models import Payment, PaymentMethod, Refund


class PaymentFilter(django_filters.FilterSet):
    """Filter for payments"""
    
    # Date filters
    date_from = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')
    
    # Amount filters
    amount_min = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_max = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    
    # Status and type filters
    status_name = django_filters.CharFilter(field_name='status__name')
    transaction_type = django_filters.CharFilter(field_name='transaction_type')
    
    # Related entity filters
    business_id = django_filters.UUIDFilter(field_name='business_id')
    client_id = django_filters.NumberFilter(field_name='client_id')
    appointment_id = django_filters.NumberFilter(field_name='appointment_id')
    payment_method_id = django_filters.NumberFilter(field_name='payment_method_id')
    
    # Boolean filters
    is_completed = django_filters.BooleanFilter(method='filter_is_completed')
    is_pending = django_filters.BooleanFilter(method='filter_is_pending')
    is_failed = django_filters.BooleanFilter(method='filter_is_failed')
    is_refunded = django_filters.BooleanFilter(method='filter_is_refunded')
    
    # Search filters
    search = django_filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Payment
        fields = [
            'date_from', 'date_to', 'amount_min', 'amount_max',
            'status_name', 'transaction_type', 'business_id', 'client_id',
            'appointment_id', 'payment_method_id', 'is_completed',
            'is_pending', 'is_failed', 'is_refunded', 'search'
        ]
    
    def filter_is_completed(self, queryset, name, value):
        if value:
            return queryset.filter(status__name='completed')
        return queryset.exclude(status__name='completed')
    
    def filter_is_pending(self, queryset, name, value):
        if value:
            return queryset.filter(status__name='pending')
        return queryset.exclude(status__name='pending')
    
    def filter_is_failed(self, queryset, name, value):
        if value:
            return queryset.filter(status__name='failed')
        return queryset.exclude(status__name='failed')
    
    def filter_is_refunded(self, queryset, name, value):
        if value:
            return queryset.filter(status__name__in=['refunded', 'partially_refunded'])
        return queryset.exclude(status__name__in=['refunded', 'partially_refunded'])
    
    def filter_search(self, queryset, name, value):
        """Search across payment ID, client name, and external transaction ID"""
        if value:
            return queryset.filter(
                Q(payment_id__icontains=value) |
                Q(client__first_name__icontains=value) |
                Q(client__last_name__icontains=value) |
                Q(external_transaction_id__icontains=value) |
                Q(appointment__service__name__icontains=value)
            )
        return queryset


class PaymentMethodFilter(django_filters.FilterSet):
    """Filter for payment methods"""
    
    payment_type = django_filters.CharFilter(field_name='payment_type')
    is_active = django_filters.BooleanFilter(field_name='is_active')
    is_default = django_filters.BooleanFilter(field_name='is_default')
    business_id = django_filters.UUIDFilter(field_name='business_id')
    
    class Meta:
        model = PaymentMethod
        fields = ['payment_type', 'is_active', 'is_default', 'business_id']


class RefundFilter(django_filters.FilterSet):
    """Filter for refunds"""
    
    # Date filters
    date_from = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')
    
    # Amount filters
    amount_min = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_max = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    
    # Type and reason filters
    refund_type = django_filters.CharFilter(field_name='refund_type')
    refund_reason = django_filters.CharFilter(field_name='refund_reason')
    status_name = django_filters.CharFilter(field_name='status__name')
    
    # Related entity filters
    payment_id = django_filters.NumberFilter(field_name='payment_id')
    business_id = django_filters.UUIDFilter(field_name='payment__business_id')
    client_id = django_filters.NumberFilter(field_name='payment__client_id')
    
    class Meta:
        model = Refund
        fields = [
            'date_from', 'date_to', 'amount_min', 'amount_max',
            'refund_type', 'refund_reason', 'status_name',
            'payment_id', 'business_id', 'client_id'
        ]
