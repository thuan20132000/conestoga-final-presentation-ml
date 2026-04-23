from rest_framework import serializers
from .models import ServiceCategory, Service


class ServiceCategorySerializer(serializers.ModelSerializer):
    """Serializer for ServiceCategory model"""
    
    total_services = serializers.SerializerMethodField()
    class Meta:
        model = ServiceCategory
        fields = [
            'id', 'name', 'description', 'sort_order', 'is_active', 'created_at', 'total_services', 'color_code', 'icon', 'image', 'business'
        ]
        read_only_fields = ['id', 'created_at']

    def get_total_services(self, obj):
        return obj.services.filter(is_active=True, business=obj.business).count()

class ServiceCategoryCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating service categories"""
    
    class Meta:
        model = ServiceCategory
        fields = [
            'name', 
            'description', 
            'sort_order', 
            'is_active', 
            'is_online_booking',
            'color_code', 
            'icon', 
            'image', 
            'business'
        ]
    
    def validate(self, data):
        business = self.context.get('business')
        if business and ServiceCategory.objects.filter(business=business).exists():
            raise serializers.ValidationError(
                "A service category with this business already exists."
            )
        return data

class ServiceSerializer(serializers.ModelSerializer):
    """Serializer for Service model"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Service
        fields = [
            'id', 'category', 'category_name', 'name', 'description', 
            'duration_minutes', 'price', 'is_active', 'requires_staff', 
            'max_capacity', 'is_online_booking', 'created_at', 'updated_at',
            'sort_order', 'color_code', 'icon', 'image'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class ServiceCategoryWithServicesSerializer(serializers.ModelSerializer):
    """Serializer for ServiceCategory model with services"""
    services = serializers.SerializerMethodField()
    
    class Meta:
        model = ServiceCategory
        fields = [
            'id', 'name', 'description', 'sort_order', 'is_active', 'is_online_booking', 'created_at', 'services', 'color_code', 'icon', 'image'
        ]
        read_only_fields = ['id', 'created_at']

    def get_services(self, obj):
        return ServiceSerializer(obj.services.all(), many=True).data

class ServiceCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating services"""
    
    class Meta:
        model = Service
        fields = [
            'category',
            'name', 
            'description', 
            'duration_minutes', 
            'price',
            'is_online_booking',
            'is_active', 
            'requires_staff', 
            'max_capacity', 
            'color_code', 
            'icon', 
            'image',
            'business'
        ]
    
    def validate(self, data):
        # Ensure the category belongs to the same business
        if 'category' in data:
            category = data['category']
            business = self.context.get('business')
            if business and category.business != business:
                raise serializers.ValidationError(
                    "Service category must belong to the same business."
                )
        return data

class CalendarServiceCategorySerializer(ServiceCategorySerializer):
    """Serializer for calendar services"""
    services = serializers.SerializerMethodField()
    
    class Meta:
        model = ServiceCategory
        fields = [
            'id', 'name', 'description', 'sort_order', 'is_active', 'is_online_booking', 'created_at', 'color_code', 'icon', 'image', 'services'
        ]
        read_only_fields = ['id', 'created_at']

    def get_services(self, obj):
        return ServiceSerializer(obj.services.filter(is_active=True, business=obj.business), many=True).data
    
    
# Business booking serializer
class BusinessBookingServiceCategorySerializer(serializers.ModelSerializer):
    """Serializer for business booking service categories"""
    services = serializers.SerializerMethodField()
    
    class Meta:
        model = ServiceCategory
        fields = [
            'id', 
            'business',
            'name', 
            'description', 
            'sort_order', 
            'is_active', 
            'is_online_booking', 
            'created_at', 
            'color_code', 
            'icon', 
            'image', 
            'services', 
        ]
        read_only_fields = ['id', 'created_at']

    def get_services(self, obj):
        business_services = Service.objects.filter(
            category=obj, 
            is_active=True,
            business=obj.business,
            is_online_booking=True
        )
        return ServiceSerializer(business_services, many=True).data
    
