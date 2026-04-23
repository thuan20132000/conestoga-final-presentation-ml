from rest_framework import serializers
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .models import Appointment, AppointmentService
from business.models import Business
from service.models import Service
from staff.models import Staff
from payment.models import Payment

class AppointmentSerializer(serializers.ModelSerializer):
    """Serializer for Appointment model"""
    client_name = serializers.CharField(
        source='client.get_full_name', read_only=True)
    business_name = serializers.CharField(
        source='business.name', read_only=True)
    client_email = serializers.EmailField(
        source='client.email', read_only=True)
    client_phone = serializers.CharField(source='client.phone', read_only=True)
    client_minimum_booking_duration = serializers.IntegerField(
        source='client.minimum_booking_duration_minutes', 
        read_only=True, 
    )
    client_notes = serializers.CharField(
        source='client.notes', read_only=True)
    business_phone_number = serializers.CharField(
        source='business.phone_number', read_only=True)
    business_twilio_phone_number = serializers.CharField(
        source='business.twilio_phone_number', read_only=True)
    business_google_review_url = serializers.URLField(
        source='business.google_review_url', read_only=True)
    class Meta:
        model = Appointment
        fields = [
            'id',
            'business',
            'business_name',
            'business_phone_number',
            'business_twilio_phone_number',
            'business_google_review_url',
            'client',
            'client_name',
            'client_email',
            'client_phone',
            'client_minimum_booking_duration',
            'client_notes',
            'appointment_date',
            'status',
            'notes',
            'internal_notes',
            'booked_by',
            'booking_source',
            'start_at',
            'end_at',
            'created_at',
            'updated_at',
            'confirmed_at',
            'completed_at',
            'cancelled_at',
            'is_active',
            'payment_status',
            'send_review_request',
            'checked_in_at'
        ]
        read_only_fields = [
            'id', 
            'created_at', 
            'updated_at',
            'checked_in_at',
            'confirmed_at', 
            'completed_at', 
            'cancelled_at', 
            'is_active', 
            'send_review_request'
        ]

    def validate(self, data):
        """Validate appointment data"""
        return data


class AppointmentUpdateSerializer(AppointmentSerializer):
    """Serializer for creating appointments"""
    class Meta:
        model = Appointment
        fields = [
            'business', 'client', 'appointment_date', 'status', 'notes', 'internal_notes', 'booked_by', 'booking_source', 'is_active', 'metadata', 'checked_in_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at',
                            'confirmed_at', 'completed_at', 'cancelled_at']
        extra_kwargs = {
            'client': {'required': True},
            'appointment_date': {'required': True},
            'status': {'required': True},
        }

    def validate(self, data):
        """Validate appointment data"""
        return data

    def update(self, instance, validated_data, metadata=None):
        """Update appointment with automatic status setting"""
        try:
            appointment = super().update(instance, validated_data)
            print("updated appointment", appointment)
            return AppointmentDetailSerializer(appointment).data
        except Exception as e:
            raise serializers.ValidationError(str(e))


class AppointmentCreateSerializer(AppointmentSerializer):
    """Serializer for creating appointments"""
    class Meta:
        model = Appointment
        fields = '__all__'

    def create(self, validated_data):
        """Create appointment with automatic status setting"""
        appointment = super().create(validated_data)
        return AppointmentDetailSerializer(appointment).data


class AppointmentServiceSerializer(serializers.ModelSerializer):
    """Serializer for AppointmentService model"""
    service_name = serializers.CharField(source='service.name', read_only=True)
    service_duration = serializers.IntegerField(
        source='service.duration_minutes', read_only=True)
    service_price = serializers.DecimalField(
        source='service.price', read_only=True, max_digits=10, decimal_places=2)
    service_color_code = serializers.CharField(
        source='service.color_code', read_only=True)
    staff_name = serializers.CharField(
        source='staff.first_name', read_only=True)
    client_name = serializers.CharField(
        source='appointment.client.get_full_name', read_only=True)

    class Meta:
        model = AppointmentService
        fields = [
            'id',
            'appointment',
            'service',
            'service_name',
            'service_duration',
            'service_price',
            'service_color_code',
            'staff',
            'staff_name',
            'client_name',
            'is_staff_request',
            'custom_price',
            'custom_duration',
            'start_at',
            'end_at',
            'created_at',
            'updated_at',
            'is_active',
            'tip_amount',
            'metadata'
        ]
        read_only_fields = ['id', 'created_at']


class AppointmentListSerializer(AppointmentSerializer):
    """Simplified serializer for appointment lists"""

    appointment_services = AppointmentServiceSerializer(
        many=True, read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id',
            'client_name',
            'business_name',
            'appointment_date',
            'status',
            'notes',
            'internal_notes',
            'booked_by',
            'booking_source',
            'is_active',
            'created_at',
            'updated_at',
            'confirmed_at',
            'completed_at',
            'cancelled_at',
            'appointment_services',
            'tip_amount'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at',
                            'confirmed_at', 'completed_at', 'cancelled_at']
        extra_kwargs = {
            'client_name': {'read_only': True},
            'business_name': {'read_only': True},
        }


class AppointmentAvailabilitySerializer(serializers.Serializer):
    """Serializer for checking appointment availability"""
    business = serializers.PrimaryKeyRelatedField(
        queryset=Business.objects.all())
    service = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all())
    appointment_date = serializers.DateField()
    staff = serializers.PrimaryKeyRelatedField(
        queryset=Staff.objects.all(),
        required=False,
        allow_null=True
    )

    def validate_appointment_date(self, value):
        """Validate appointment date"""
        if value < timezone.now().date():
            raise serializers.ValidationError(_("Date cannot be in the past"))
        return value

    def validate(self, data):
        """Validate availability data"""
        business = data['business']
        service = data['service']
        appointment_date = data['appointment_date']
        staff = data.get('staff')

        # Check if business is open on this date
        day_of_week = appointment_date.weekday()
        operating_hours = business.operating_hours.filter(
            day_of_week=day_of_week).first()

        if not operating_hours or not operating_hours.is_open:
            raise serializers.ValidationError(
                _("Business is closed on this date"))

        return data


class AppointmentStatsSerializer(serializers.Serializer):
    """Serializer for appointment statistics"""
    total_appointments = serializers.IntegerField()
    completed_appointments = serializers.IntegerField()
    cancelled_appointments = serializers.IntegerField()
    upcoming_appointments = serializers.IntegerField()
    today_appointments = serializers.IntegerField()
    revenue_today = serializers.DecimalField(max_digits=10, decimal_places=2)
    revenue_this_month = serializers.DecimalField(
        max_digits=10, decimal_places=2)
    average_appointment_value = serializers.DecimalField(
        max_digits=10, decimal_places=2)
    no_show_rate = serializers.DecimalField(max_digits=5, decimal_places=2)


class AppointmentPaymentSerializer(serializers.ModelSerializer):
    
    payment_method_name = serializers.CharField(source='payment_method.name', read_only=True)
    payment_method_type = serializers.CharField(source='payment_method.payment_type', read_only=True)
    class Meta:
        model = Payment
        fields = [
            'id', 
            'payment_method', 
            'payment_method_name', 
            'payment_method_type', 
            'amount', 
            'currency', 
            'external_transaction_id', 
            'processing_fee',
            'net_amount', 'created_at',
            'updated_at', 
            'processed_at', 
            'completed_at', 
            'processed_by', 
            'notes',
             'internal_notes', 
            'status'
        ]
        read_only_fields = ['created_at', 'updated_at'] 

class AppointmentDetailSerializer(AppointmentSerializer):
    """Serializer for detail view of appointment"""
    appointment_services = AppointmentServiceSerializer(
        many=True, read_only=True)
    start_at = serializers.DateTimeField(
        source='appointment_services.first.start_at', read_only=True)
    latest_payment = serializers.SerializerMethodField()
    class Meta(AppointmentSerializer.Meta):

        fields = AppointmentSerializer.Meta.fields + [
            'start_at',
            'appointment_services',
            'latest_payment'
        ]
        read_only_fields = AppointmentSerializer.Meta.read_only_fields + \
            ['start_at']
    
    def get_latest_payment(self, obj):
        if obj.payments.exists():
            return AppointmentPaymentSerializer(obj.payments.order_by('-created_at').first()).data
        else:
            return None


class AppointmentHistorySerializer(serializers.ModelSerializer):
    """Serializer for history of an appointment"""
    client_name = serializers.CharField(
        source='client.get_full_name', read_only=True)

    class Meta:
        model = Appointment.history.model
        fields = '__all__'

class BusinessTicketReportSummarySerializer(serializers.Serializer):
    """Serializer for ticket report summary"""
    total_sales = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_tips = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_cash_tips = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    total_card_tips = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    total_services = serializers.IntegerField()
    total_staffs = serializers.IntegerField( required=False )
    from_date = serializers.DateField( required=False )
    to_date = serializers.DateField( required=False )
    payment_stats = serializers.JSONField(required=False)

class StaffTicketReportSummarySerializer(serializers.Serializer):
    """Serializer for staff ticket report summary"""
    total_sales = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_tips = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_cash_tips = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    total_card_tips = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    total_services = serializers.IntegerField()

class TicketReportDataSerializer(serializers.Serializer):
    """Serializer for ticket report data"""
    staff =serializers.IntegerField()
    staff_first_name = serializers.CharField()
    staff_last_name = serializers.CharField()
    total_service_sales = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_service_tips = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_services = serializers.IntegerField()
    appointment_date = serializers.DateField( required=False )
    
class TicketReportStaffDataSerializer(serializers.Serializer):
    """Serializer for ticket report staff data"""
    staff = serializers.IntegerField()
    staff_first_name = serializers.CharField()
    staff_last_name = serializers.CharField()
    appointment_id = serializers.IntegerField( required=False )
    service_id = serializers.IntegerField( required=False )
    service_name = serializers.CharField( required=False )
    service_duration = serializers.IntegerField( required=False )
    custom_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False )
    tip_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False )
    tip_method = serializers.CharField( required=False )
    client_name = serializers.CharField( required=False )
    updated_at = serializers.DateTimeField( required=False )
    created_at = serializers.DateTimeField( required=False )
    
class BusinessTicketReportSerializer(serializers.Serializer):
    """Serializer for ticket report summary"""
    summary = BusinessTicketReportSummarySerializer()
    data = TicketReportDataSerializer(many=True)
    
class StaffTicketReportSerializer(serializers.Serializer):
    """Serializer for staff ticket report"""
    summary = StaffTicketReportSummarySerializer()
    data = TicketReportStaffDataSerializer(many=True)

# Salary Report Serializers
class SalaryReportSummaryDataSerializer(serializers.Serializer):
    """Serializer for individual staff data in salary report summary"""
    staff = serializers.IntegerField()
    staff_first_name = serializers.CharField()
    staff_last_name = serializers.CharField()
    total_service_sales = serializers.DecimalField(max_digits=10, decimal_places=2)
    commission_rate = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    commission_amount = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    total_services = serializers.IntegerField()
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)

class BusinessSalaryReportSummarySerializer(serializers.Serializer):
    """Serializer for business-level salary report summary"""
    total_sales = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_commission = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    total_services = serializers.IntegerField()
    total_staffs = serializers.IntegerField()
    from_date = serializers.DateField()
    to_date = serializers.DateField()

class SalaryReportSerializer(serializers.Serializer):
    """Serializer for salary report summary with commission"""
    summary = BusinessSalaryReportSummarySerializer()
    data = SalaryReportSummaryDataSerializer(many=True)

class SalaryReportByDatesDataSerializer(serializers.Serializer):
    """Serializer for daily breakdown in salary report"""
    staff = serializers.IntegerField()
    staff_first_name = serializers.CharField()
    staff_last_name = serializers.CharField()
    appointment_date = serializers.DateField()
    total_service_sales = serializers.DecimalField(max_digits=10, decimal_places=2)
    commission_rate = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    commission_amount = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    total_services = serializers.IntegerField()

class StaffSalaryReportSummarySerializer(serializers.Serializer):
    """Serializer for staff salary report summary"""
    total_sales = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_commission = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    total_tips = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_cash_tips = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    total_card_tips = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    total_services = serializers.IntegerField()
    commission_rate = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)

class SalaryReportByDatesSerializer(serializers.Serializer):
    """Serializer for salary report with daily breakdown"""
    summary = StaffSalaryReportSummarySerializer()
    data = SalaryReportByDatesDataSerializer(many=True)

class SalaryReportByDateDataSerializer(serializers.Serializer):
    """Serializer for detailed service-level data in salary report by date"""
    staff = serializers.IntegerField()
    staff_first_name = serializers.CharField()
    staff_last_name = serializers.CharField()
    appointment_id = serializers.IntegerField(required=False)
    service_id = serializers.IntegerField(required=False)
    service_name = serializers.CharField(required=False)
    service_duration = serializers.IntegerField(required=False)
    custom_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    commission_rate = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    commission_amount = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    tip_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    tip_method = serializers.CharField(required=False)
    client_name = serializers.CharField(required=False)
    updated_at = serializers.DateTimeField(required=False)
    created_at = serializers.DateTimeField(required=False)

class SalaryReportByDateSerializer(serializers.Serializer):
    """Serializer for detailed salary report by specific date"""
    summary = StaffSalaryReportSummarySerializer()
    data = SalaryReportByDateDataSerializer(many=True)