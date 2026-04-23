from rest_framework import serializers
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .models import Review
from appointment.models import Appointment, AppointmentStatusType
from appointment.serializers import AppointmentDetailSerializer


class ReviewSerializer(serializers.ModelSerializer):
    """Serializer for Review model"""
    appointment_details = AppointmentDetailSerializer(
        source='appointment',
        read_only=True
    )
    
    class Meta:
        model = Review
        fields = [
            'id',
            'appointment',
            'appointment_details',
            'rating',
            'comment',
            'is_visible',
            'is_verified',
            'reviewed_at',
            'is_active',
            'created_at',
            'updated_at',
            'metadata'
        ]
        read_only_fields = [
            'id',
            'is_verified',
            'reviewed_at',
            'created_at',
            'updated_at'
        ]
    
    def validate_appointment(self, value):
        """Validate that appointment exists and is completed"""
        if not value:
            raise serializers.ValidationError(_("Appointment is required."))
        
        # Check if appointment is cancelled
        if value.status == AppointmentStatusType.CANCELLED:
            raise serializers.ValidationError(
                _("Cannot review a cancelled appointment.")
            )
            
        if Review.objects.filter(appointment=value).exists():
            raise serializers.ValidationError(_("A review already exists for this appointment."))
        
        return value
    

    
    def validate_rating(self, value):
        """Validate rating is between 1 and 5"""
        if value < 1 or value > 5:
            raise serializers.ValidationError(_("Rating must be between 1 and 5."))
        return value

    

class ReviewCreateSerializer(ReviewSerializer):
    """Serializer for creating reviews"""
    
    class Meta(ReviewSerializer.Meta):
        fields = [
            'appointment',
            'rating',
            'comment',
            'is_visible',
            'metadata'
        ]
        extra_kwargs = {
            'appointment': {'required': True},
            'rating': {'required': True},
        }
    
    def create(self, validated_data):
        """Create review with automatic verification"""
        review = Review.objects.create(**validated_data)
        return review


class ReviewListSerializer(serializers.ModelSerializer):
    """Simplified serializer for review lists"""
    appointment_date = serializers.DateField(source='appointment.appointment_date', read_only=True)
    business_name = serializers.CharField(source='appointment.business.name', read_only=True)
    appointment_details = AppointmentDetailSerializer(
        source='appointment',
        read_only=True
    )
    class Meta:
        model = Review
        fields = [
            'id',
            'appointment_date',
            'business_name',
            'appointment',
            'appointment_details',
            'rating',
            'comment',
            'is_visible',
            'is_verified',
            'reviewed_at',
            'created_at'
        ]
        read_only_fields = ['id', 'reviewed_at', 'created_at', 'appointment']
        
class ReviewDetailSerializer(ReviewSerializer):
    """Serializer for detailed review view"""
    pass


class ReviewStatsSerializer(serializers.Serializer):
    """Serializer for review statistics"""
    total_reviews = serializers.IntegerField()
    average_rating = serializers.FloatField()
    rating_distribution = serializers.DictField()
    verified_reviews = serializers.IntegerField()
    visible_reviews = serializers.IntegerField()
    recent_reviews = serializers.IntegerField()

