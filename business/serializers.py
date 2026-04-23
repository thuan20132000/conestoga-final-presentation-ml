from rest_framework import serializers
from django.db.models import Sum, Avg
from django.db import transaction
from .models import (
    BusinessType,
    Business,
    OperatingHours,
    BusinessSettings,
    BusinessRoles,
    BusinessOnlineBooking,
    BusinessBanner,
    BusinessFeedback,
)
from payment.serializers import PaymentMethodSerializer, PaymentGatewaySerializer
from subscription.serializers import BusinessSubscriptionSerializer
from staff.models import Staff
from staff.services import StaffCredentialService

class BusinessTypeSerializer(serializers.ModelSerializer):
    """Serializer for BusinessType model"""
    
    class Meta:
        model = BusinessType
        fields = ['id', 'name', 'description', 'icon', 'created_at']
        read_only_fields = ['id', 'created_at']


class OperatingHoursSerializer(serializers.ModelSerializer):
    """Serializer for OperatingHours model"""
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)
    
    class Meta:
        model = OperatingHours
        fields = [
            'id', 'day_of_week', 'day_name', 'is_open', 'open_time', 
            'close_time', 'is_break_time', 'break_start_time', 'break_end_time',
            'business'
        ]
        read_only_fields = ['id', 'business']


class BusinessSettingsSerializer(serializers.ModelSerializer):
    """Serializer for BusinessSettings model"""
    
    class Meta:
        model = BusinessSettings
        fields = [
            'id', 'timezone', 'advance_booking_days', 'min_advance_booking_hours', 
            'max_advance_booking_days', 'time_slot_interval', 'buffer_time_minutes',
            'send_reminder_emails', 'send_reminder_sms', 'reminder_hours_before',
            'send_confirmation_sms', 'send_confirmation_email', 'send_cancellation_sms',
            'send_cancellation_email',
            'preferred_language',
            'currency', 'tax_rate', 'require_payment_advance', 'allow_online_booking',
            'require_client_phone', 'require_client_email', 'auto_confirm_appointments',
            'allow_online_gift_cards', 'gift_card_processing_fee_enabled', 'tax_with_cash_enabled',
            'half_turn_threshold',
        ]
        read_only_fields = ['id']


class BusinessSerializer(serializers.ModelSerializer):
    """Serializer for Business model"""
    
    class Meta:
        model = Business
        fields = [
            'id', 'name', 'business_type', 'phone_number', 'email', 'website', 'address', 'city', 'state_province', 'postal_code', 'country', 'description', 'logo', 'google_review_url', 'created_at', 'updated_at', 'enable_ai_assistant', 'twilio_phone_number']
        read_only_fields = ['id', 'created_at', 'updated_at']


class BusinessListSerializer(serializers.ModelSerializer):
    """Simplified serializer for business list views"""
    business_type_name = serializers.CharField(source='business_type.name', read_only=True)
    
    class Meta:
        model = Business
        fields = [
            'id', 'name', 'business_type', 'business_type_name', 'phone_number',
            'email', 'city', 'state_province', 'country', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class BusinessOnlineBookingSerializer(serializers.ModelSerializer):
    """Serializer for BusinessOnlineBooking model"""
    class Meta:
        model = BusinessOnlineBooking
        fields = ['id', 'business', 'name', 'slug', 'logo', 'description', 'policy', 'interval_minutes', 'buffer_time_minutes', 'is_active', 'shareable_link']
        read_only_fields = ['id', 'shareable_link']

class BusinessDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for business detail views"""
    business_type_name = serializers.CharField(source='business_type.name', read_only=True)
    operating_hours = OperatingHoursSerializer(many=True, read_only=True)
    settings = BusinessSettingsSerializer(read_only=True)
    online_booking = BusinessOnlineBookingSerializer(read_only=True)
    subscription = BusinessSubscriptionSerializer(read_only=True)
    
    class Meta:
        model = Business
        fields = [
            'id', 'name', 'business_type', 'business_type_name', 'phone_number',
            'email', 'website', 'address', 'city', 'state_province', 'postal_code',
            'country', 'description', 'logo', 'google_review_url', 'operating_hours',
            'settings', 'online_booking', 'subscription', 'created_at', 'updated_at',
            'enable_ai_assistant',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BusinessCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating businesses"""
    operating_hours = OperatingHoursSerializer(many=True, required=False)
    settings = BusinessSettingsSerializer(required=False)
    
    class Meta:
        model = Business
        fields = [
            'name', 'business_type', 'phone_number', 'email', 'website',
            'address', 'city', 'state_province', 'postal_code', 'country',
            'description', 'logo', 'google_review_url', 'operating_hours', 'settings'
        ]
    
    def create(self, validated_data):
        operating_hours_data = validated_data.pop('operating_hours', [])
        settings_data = validated_data.pop('settings', {})
        
        business = Business.objects.create(**validated_data)
        
        # Create default operating hours for all days
        if not operating_hours_data:
            for day in range(7):
                OperatingHours.objects.create(
                    business=business,
                    day_of_week=day,
                    is_open=True if day < 5 else False,  # Open weekdays, closed weekends
                    open_time='09:00' if day < 5 else None,
                    close_time='17:00' if day < 5 else None
                )
        else:
            for hours_data in operating_hours_data:
                OperatingHours.objects.create(business=business, **hours_data)
        
        # Create default settings
        BusinessSettings.objects.create(business=business, **settings_data)
        
        return business
    
    def update(self, instance, validated_data):
        operating_hours_data = validated_data.pop('operating_hours', None)
        settings_data = validated_data.pop('settings', None)
        
        # Update business fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update operating hours if provided
        if operating_hours_data is not None:
            instance.operating_hours.all().delete()
            for hours_data in operating_hours_data:
                OperatingHours.objects.create(business=instance, **hours_data)
        
        # Update settings if provided
        if settings_data is not None:
            settings, created = BusinessSettings.objects.get_or_create(business=instance)
            for attr, value in settings_data.items():
                setattr(settings, attr, value)
            settings.save()
        
        return instance


class ReceptionistStatisticsSerializer(serializers.Serializer):
    """Serializer for business receptionist statistics"""
    total_calls = serializers.SerializerMethodField()
    unsuccessful_calls = serializers.SerializerMethodField()
    negative_sentiment_calls = serializers.SerializerMethodField()
    total_cost = serializers.SerializerMethodField()
    average_cost = serializers.SerializerMethodField()
    recent_calls = serializers.SerializerMethodField()
    
    
    def get_total_calls(self, business_calls):
        return business_calls.count()
    
    def get_unsuccessful_calls(self, business_calls):
        return business_calls.filter(outcome='unsuccessful').count()
    
    def get_negative_sentiment_calls(self, business_calls):
        return business_calls.filter(sentiment='negative').count()
    
    def get_total_cost(self, business_calls):
        total_cost = business_calls.aggregate(total_cost=Sum('cost'))['total_cost'] or 0.0
        return round(total_cost, 2)
    
    def get_average_cost(self, business_calls):
        total_cost = self.get_total_cost(business_calls)
        total_calls = self.get_total_calls(business_calls)
        if total_calls > 0:
            return round(total_cost / total_calls, 4)
        return 0.0

    def get_recent_calls(self, business_calls):
        recent_calls = business_calls.order_by('-started_at')[:15]
        return recent_calls.values(
            'id', 
            'started_at', 
            'ended_at', 
            'duration_seconds', 
            'cost', 
            'outcome', 
            'sentiment',
            'direction', 
            'caller_number', 
            'receiver_number', 
            'call_sid', 
            'status', 
            'transcript_summary',
            'conversation_transcript',
            'category',
        )

class AppointmentKPISerializer(serializers.Serializer):
    count = serializers.IntegerField()
    change_percentage = serializers.FloatField(allow_null=True)


class RevenueKPISerializer(serializers.Serializer):
    amount = serializers.FloatField()
    change_percentage = serializers.FloatField(allow_null=True)


class CustomerKPISerializer(serializers.Serializer):
    count = serializers.IntegerField()
    new_this_week = serializers.IntegerField()
    change_percentage = serializers.FloatField(allow_null=True)


class RatingKPISerializer(serializers.Serializer):
    value = serializers.FloatField(allow_null=True)
    review_count = serializers.IntegerField()


class CountKPISerializer(serializers.Serializer):
    count = serializers.IntegerField()


class TodaysAppointmentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    client_name = serializers.CharField(allow_null=True)
    start_at = serializers.DateTimeField(allow_null=True)
    booking_source = serializers.CharField()
    services = serializers.ListField(child=serializers.CharField())


class AppointmentsByStatusSerializer(serializers.Serializer):
    scheduled = serializers.IntegerField()
    in_service = serializers.IntegerField()
    checked_in = serializers.IntegerField()
    checked_out = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    no_show = serializers.IntegerField()
    pending_payment = serializers.IntegerField()


class BookingSourcesSerializer(serializers.Serializer):
    online = serializers.IntegerField()
    phone = serializers.IntegerField()
    walk_in = serializers.IntegerField()
    staff = serializers.IntegerField()
    ai_receptionist = serializers.IntegerField()


class RevenueByMethodSerializer(serializers.Serializer):
    method = serializers.CharField()
    amount = serializers.FloatField()


class StaffPerformanceSerializer(serializers.Serializer):
    staff_id = serializers.IntegerField()
    name = serializers.CharField()
    total_completed_services = serializers.IntegerField()
    total_services_requested = serializers.IntegerField()
    sales = serializers.FloatField()


class DailyTrendSerializer(serializers.Serializer):
    date = serializers.DateField()
    appointments = serializers.IntegerField()
    revenue = serializers.FloatField()


class BusinessDashboardSerializer(serializers.Serializer):
    """Serializer for business dashboard KPI metrics."""
    total_appointments = AppointmentKPISerializer()
    total_revenue = RevenueKPISerializer()
    total_customers = CustomerKPISerializer()
    average_rating = RatingKPISerializer()
    completed_payments = CountKPISerializer()
    active_staff = CountKPISerializer()
    todays_appointments = TodaysAppointmentSerializer(many=True)
    appointments_by_status = AppointmentsByStatusSerializer()
    booking_sources = BookingSourcesSerializer()
    revenue_by_payment_method = RevenueByMethodSerializer(many=True)
    total_tips = serializers.FloatField()
    average_ticket_value = serializers.FloatField()
    cancellation_rate = serializers.FloatField()
    no_show_rate = serializers.FloatField()
    staff_performance = StaffPerformanceSerializer(many=True)
    daily_trends = DailyTrendSerializer(many=True)


class BusinessManagementSerializer(BusinessDetailSerializer):
    """Serializer for business dashboard"""
    
    payment_methods = PaymentMethodSerializer(many=True, read_only=True)
    payment_gateway = PaymentGatewaySerializer(source='payment_gateways.first', read_only=True)
    class Meta(BusinessDetailSerializer.Meta):
        fields = BusinessDetailSerializer.Meta.fields + ['payment_methods', 'payment_gateway']
        read_only_fields = BusinessDetailSerializer.Meta.read_only_fields + ['payment_methods', 'payment_gateway']


class BusinessRolesSerializer(serializers.ModelSerializer):
    """Serializer for BusinessRoles model"""
    class Meta:
        model = BusinessRoles
        fields = ['id', 'name', 'description']
        read_only_fields = ['id']
        
class BusinessBannerSerializer(serializers.ModelSerializer):
    """Serializer for BusinessBanner model"""
    class Meta:
        model = BusinessBanner
        fields = [
            'id', 
            'type',
            'background_color', 
            'text_color', 
            'image', 
            'title', 
            'message', 
            'cta_text', 
            'cta_url', 
            'start_at', 
            'end_at', 
            'is_active',
            'is_visible',
            'dismissible',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'is_visible']

    def get_is_visible(self, obj):
        return obj.is_visible()

class BusinessInfoSerializer(serializers.ModelSerializer):
    """Serializer for BusinessInfo model"""
    
    operating_hours = OperatingHoursSerializer(many=True, read_only=True)
    settings = BusinessSettingsSerializer(read_only=True)
    online_booking = BusinessOnlineBookingSerializer(read_only=True)
    active_banner = serializers.SerializerMethodField()
    class Meta:
        model = Business
        fields = [
            'id', 
            'name', 
            'phone_number', 
            'email', 
            'website', 
            'address', 
            'city', 
            'state_province', 
            'postal_code', 
            'country', 
            'description', 
            'logo',
            'google_review_url',
            'currency',
            'cost_per_minute',
            'status',
            'operating_hours',
            'settings',
            'online_booking',
            'active_banner'
        ]
        read_only_fields = ['id']

    def get_active_banner(self, obj):
        return BusinessBannerSerializer(obj.banners.filter(is_active=True).first()).data
    
    
class OwnerRegisterSerializer(serializers.Serializer):
    """Serializer for owner registration"""
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    phone = serializers.CharField(required=True)
    email = serializers.EmailField(required=False)


class BusinessSettingsRegisterSerializer(serializers.Serializer):
    """Serializer for business settings"""
    timezone = serializers.ChoiceField(
        choices=BusinessSettings.TIMEZONE_CHOICES, 
        default="America/Toronto"
    )
    advance_booking_days = serializers.IntegerField(required=False, default=30)
    min_advance_booking_hours = serializers.IntegerField(required=False, default=2)
    max_advance_booking_days = serializers.IntegerField(required=False, default=90)
    time_slot_interval = serializers.IntegerField(required=False, default=15)
    buffer_time_minutes = serializers.IntegerField(required=False, default=0)
    currency = serializers.ChoiceField(
        choices=Business.CURRENCY_CHOICES, 
        default="CAD"
    )


    class Meta:
        fields = ['timezone', 'advance_booking_days', 'min_advance_booking_hours', 'max_advance_booking_days', 'time_slot_interval', 'buffer_time_minutes']
        
        

class BusinessRegisterSerializer(serializers.Serializer):
    """
    Serializer orchestrating business + owner registration in one request.
    """

    business = BusinessSerializer()
    owner = OwnerRegisterSerializer()
    settings = BusinessSettingsRegisterSerializer()
    
    
    class Meta:
        fields = ['business', 'owner', 'settings']
        read_only_fields = ['business', 'owner', 'settings']


class GoogleBusinessRegisterSerializer(serializers.Serializer):
    """
    Serializer for Google-based business registration.
    Owner identity (name, email) is extracted from the verified Google token.
    """
    google_id_token = serializers.CharField(required=True)
    business = BusinessSerializer()
    settings = BusinessSettingsRegisterSerializer()

    class Meta:
        fields = ['google_id_token', 'business', 'settings']


class GoogleLoginSerializer(serializers.Serializer):
    """Serializer for Google-based staff/owner login."""
    google_id_token = serializers.CharField(required=True)

    class Meta:
        fields = ['google_id_token']


class FacebookBusinessRegisterSerializer(serializers.Serializer):
    """
    Serializer for Facebook-based business registration.
    Owner identity (name, email) is extracted from the verified Facebook token.
    """
    facebook_access_token = serializers.CharField(required=True)
    business = BusinessSerializer()
    settings = BusinessSettingsRegisterSerializer()

    class Meta:
        fields = ['facebook_access_token', 'business', 'settings']


class FacebookLoginSerializer(serializers.Serializer):
    """Serializer for Facebook-based staff/owner login."""
    facebook_access_token = serializers.CharField(required=True)

    class Meta:
        fields = ['facebook_access_token']


class BusinessFeedbackSerializer(serializers.ModelSerializer):
    """Serializer for business feedback to the platform."""
    submitted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = BusinessFeedback
        fields = [
            'id', 'business', 'submitted_by', 'submitted_by_name',
            'category', 'subject', 'message', 'status',
            'admin_response', 'admin_responded_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'business', 'submitted_by',
            'status', 'admin_response', 'admin_responded_at',
            'created_at', 'updated_at',
        ]

    def get_submitted_by_name(self, obj):
        return obj.submitted_by.get_full_name() if obj.submitted_by else None