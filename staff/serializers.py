from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from .models import Staff, StaffService, StaffWorkingHours, StaffOffDay, TimeEntry, StaffWorkingHoursOverride
from business.serializers import BusinessSettingsSerializer, BusinessSerializer


class StaffServiceSerializer(serializers.ModelSerializer):
    """Serializer for StaffService model"""
    service_name = serializers.CharField(source='service.name', read_only=True)
    service_duration = serializers.IntegerField(source='service.duration_minutes', read_only=True)
    service_price = serializers.DecimalField(source='service.price', read_only=True, max_digits=10, decimal_places=2)
    service_category_name = serializers.CharField(source='service.category.name', read_only=True)
    service_category_id = serializers.IntegerField(source='service.category_id', read_only=True)
    
    class Meta:
        model = StaffService
        fields = [
            'id', 
            'service_id', 
            'service_name', 
            'service_duration',
            'service_price',
            'service_category_name',
            'service_category_id',
            'is_primary', 
            'custom_price',
            'custom_duration',
            'is_online_booking', 
            'is_active', 
            'staff_id',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at']
    


class StaffSerializer(serializers.ModelSerializer):
    """Serializer for Staff model"""
    full_name = serializers.CharField(read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)
    class Meta:
        model = Staff
        fields = [
            'id', 
            'first_name', 
            'last_name', 
            'full_name', 'email', 'phone',
            'role','role_name', 
            'staff_code',
            'is_active',
            'is_online_booking_allowed', 
            'is_payment_processing_allowed',
            'hire_date', 'bio', 'photo',
            'created_at', 
            'updated_at', 
            'business_id', 
            'is_deleted',
            'commission_rate',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class StaffCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating staff"""
    
    class Meta:
        model = Staff
        fields = [
            'first_name', 
            'last_name', 
            'email', 
            'phone', 
            'role',
            'is_active',
            'is_online_booking_allowed',
            'is_payment_processing_allowed',
            'hire_date', 
            'bio', 
            'photo',
            'business',
            'commission_rate',
        ]
    
    def validate_email(self, value):
        if value:
            business = self.context.get('business')
            if business and Staff.objects.filter(
                business=business, email=value
            ).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise serializers.ValidationError(
                    _("A staff member with this email already exists for this business.")
                )
        return value

class StaffWorkingHoursSerializer(serializers.ModelSerializer):
    """Serializer for StaffWorkingHours model"""
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)
    is_override = serializers.BooleanField(default=False)
    class Meta:
        model = StaffWorkingHours
        fields = '__all__'
        
class StaffWorkingHoursOverrideSerializer(serializers.ModelSerializer):
    """Serializer for StaffWorkingHoursOverride model"""
    is_override = serializers.BooleanField(default=True)
    class Meta:
        model = StaffWorkingHoursOverride
        fields = ['id', 'date', 'start_time', 'end_time', 'is_working', 'reason', 'is_override', 'staff']
        
class StaffWorkingHoursCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating staff working hours"""
    class Meta:
        model = StaffWorkingHours
        fields = ['day_of_week', 'start_time', 'end_time', 'is_working']

class StaffOffDaySerializer(serializers.ModelSerializer):
    """Serializer for StaffOffDay model"""
    class Meta:
        model = StaffOffDay
        fields = '__all__'

class StaffOffDayCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating staff off days"""
    class Meta:
        model = StaffOffDay
        fields = ['start_date', 'end_date', 'reason', 'staff']


class StaffCalendarSerializer(StaffSerializer):
    """Serializer for staff calendar"""
    working_hours = serializers.SerializerMethodField()
    is_off_day = serializers.SerializerMethodField();
    class Meta:
        model = Staff
        fields = StaffSerializer.Meta.fields + ['working_hours', 'is_off_day']

    def get_working_hours(self, obj):
        """Get working hours for staff"""
        try:    
            appointment_date = self.context.get('appointment_date')
            weekday = self.context.get('weekday')
            
            # Check if there is an override for the appointment date
            override = obj.working_hours_overrides.filter(date=appointment_date).first()
            
            if override:
                return StaffWorkingHoursOverrideSerializer(override).data
            
            # Check if the staff is working on the appointment date
            working_hours = obj.working_hours.filter(day_of_week=weekday).first()
            
            if working_hours:
                return StaffWorkingHoursSerializer(working_hours).data
            else:
                return None
        
        except Exception as e:
            return None
        
    def get_is_off_day(self, obj):
        """Get if staff is off day"""
        try:
            appointment_date = self.context.get('appointment_date')
            return obj.staff_off_days.filter(start_date__lte=appointment_date, end_date__gte=appointment_date).exists()
        except Exception as e:
            return False

class LoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError(_('Unable to log in with provided credentials.'))
            if not user.is_active:
                raise serializers.ValidationError(_('User account is disabled.'))
            attrs['user'] = user
        else:
            raise serializers.ValidationError(_('Must include "username" and "password".'))
        
        return attrs


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        min_length=8,
        help_text='Password must be at least 8 characters long'
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text='Enter the same password as before, for verification'
    )
    
    class Meta:
        model = Staff
        fields = [
            'username',
            'email',
            'password',
            'password_confirm',
            'first_name',
            'last_name',
            'phone',
            'business',
        ]
        extra_kwargs = {
            'username': {'required': False},  # Will be auto-generated if not provided
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
        }
    
    def validate_email(self, value):
        """Validate that email is unique"""
        if Staff.objects.filter(email=value).exists():
            raise serializers.ValidationError(_("A user with this email already exists."))
        return value
    
    def validate(self, attrs):
        """Validate that passwords match"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': _("Password fields didn't match.")
            })
        return attrs
    
    def create(self, validated_data):
        """Create a new user with hashed password"""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        # Generate username if not provided (using email as base)
        if not validated_data.get('username'):
            email = validated_data.get('email', '')
            username_base = email.split('@')[0] if email else 'user'
            # Ensure username is unique
            username = username_base
            counter = 1
            while Staff.objects.filter(username=username).exists():
                username = f"{username_base}{counter}"
                counter += 1
            validated_data['username'] = username
        
        # Create user
        user = Staff.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        
        return user


class UserProfileSerializer(StaffSerializer):
    """Serializer for authenticated user profile"""
    business = serializers.SerializerMethodField()
    business_settings = serializers.SerializerMethodField();
    
    class Meta(StaffSerializer.Meta):
        fields = [
            'id', 
            'username',
            'first_name', 
            'last_name', 
            'full_name', 
            'email', 
            'phone',
            'role',
            'role_name',
            'staff_code',
            'business',
            'is_active',
            'is_online_booking_allowed', 
            'is_payment_processing_allowed',
            'hire_date', 
            'bio', 
            'photo',
            'created_at', 
            'updated_at',
            'business_settings',
        ]
        read_only_fields = ['id', 'username', 'created_at', 'updated_at']
        
    
    def get_business(self, obj):
        """Get business"""
        try:
            if obj.role.name in ['Owner', 'Manager','Receptionist','Stylist','Technician']:
                return BusinessSerializer(obj.business).data
            else:
                return None
        except Exception as e:
            return None
    
    def get_business_settings(self, obj):
        """Get business settings"""
        try:
            if obj.role.name in ['Owner', 'Manager','Receptionist']:
                return BusinessSettingsSerializer(obj.business.settings).data
            else:
                return None
        except Exception as e:
            return None

class BusinessBookingStaffSerializer(serializers.ModelSerializer):
    """Serializer for business booking staff"""
    role_name = serializers.CharField(source='role.name', read_only=True)
    class Meta:
        model = Staff
        fields = [
            'id', 'first_name', 'last_name','role_name'
        ]
        read_only_fields = ['id', 'created_at', 'photo', 'role_name']
        

class TimeEntryPartialUpdateSerializer(serializers.ModelSerializer):
    """Serializer for partial update time entry"""
    
    clock_in = serializers.DateTimeField(
        required=False,
        allow_null=True,
    )
    
    clock_out = serializers.DateTimeField(
        required=False,
        allow_null=True,
    )
    
    class Meta:
        model = TimeEntry
        fields = ['clock_out', 'clock_in']
        read_only_fields = ['total_minutes', 'overtime_minutes']

class TimeEntryCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating time entry"""
    class Meta:
        model = TimeEntry
        fields = ['staff', 'clock_in', 'clock_out']
        read_only_fields = ['total_minutes', 'overtime_minutes']

class TimeEntrySerializer(serializers.ModelSerializer):
    """Serializer for TimeEntry model"""
    staff_name = serializers.CharField(source='staff.first_name', read_only=True)
    staff_phone = serializers.CharField(source='staff.phone', read_only=True)
    class Meta:
        model = TimeEntry
        fields = "__all__"
        read_only_fields = (
            'clock_in',
            'clock_out',
            'total_minutes',
            'overtime_minutes',
            'status',
            'staff_name',
            'staff_phone'
        )

class TimeEntrySummarySerializer(serializers.Serializer):
    """Serializer for time entry summary"""
    total_time_entries = serializers.IntegerField()
    total_minutes = serializers.IntegerField()
    total_overtime_minutes = serializers.IntegerField()

class TimeEntryListSerializer(serializers.Serializer):
    """Serializer for time entry list"""
    data = TimeEntrySerializer(many=True)
    summary = TimeEntrySummarySerializer()