from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as filters
from .models import ServiceCategory, Service
from .serializers import (
    ServiceCategorySerializer, 
    ServiceSerializer, 
    CalendarServiceCategorySerializer, 
    ServiceCreateUpdateSerializer,
    ServiceCategoryCreateUpdateSerializer,
)
from main.viewsets import BaseModelViewSet
from rest_framework.permissions import IsAuthenticated
from staff.permissions import IsBusinessManager, IsBusinessManagerOrReceptionist


class ServiceCategoryFilter(filters.FilterSet):
    is_active = filters.BooleanFilter(field_name='is_active')
    business_id = filters.UUIDFilter(field_name='business_id',required=True)
    class Meta:
        model = ServiceCategory
        fields = ['is_active', 'business_id']

class ServiceCategoryViewSet(BaseModelViewSet):
    """ViewSet for ServiceCategory management"""
    queryset = ServiceCategory.objects.all()
    serializer_class = ServiceCategorySerializer
    filterset_class = ServiceCategoryFilter
    permission_classes = [IsAuthenticated, IsBusinessManagerOrReceptionist]
    
    def get_queryset(self):
        """Get queryset for service categories"""
        queryset = super().get_queryset().filter(is_active=True)
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create a service category"""
        try:
            print("request.data", request.data)
            serializer = ServiceCategoryCreateUpdateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            created_service_category = serializer.save()
            return self.response_success(ServiceCategorySerializer(created_service_category).data)
        except Exception as e:
            return self.response_error(str(e))
        
    def destroy(self, request, *args, **kwargs):
        """Destroy a service category"""
        try:
            instance = self.get_object()
            instance.is_active = False
            instance.save()
            return self.response_success(data=None, message="Service category deleted successfully")
        except Exception as e:
            return self.response_error(str(e))
        
    @action(detail=True, methods=['get'], url_path='services')
    def services(self, request, pk=None):
        """Get services for a category"""
        category = self.get_object()
        services = category.services.filter(is_active=True, business=request.user.business)
        serializer = ServiceSerializer(services, many=True)
        return self.response_success(serializer.data, message="Services retrieved successfully")
    
    @action(detail=False, methods=['get'], url_path='calendar-services')
    def calendar_services(self, request):
        """Get calendar services"""
        try:
            business = request.user.business
            queryset = ServiceCategory.objects.filter(
                is_active=True, 
                business=business,
            )
            serializer = CalendarServiceCategorySerializer(queryset, many=True)
            return self.response_success(serializer.data)
        except Exception as e:
            return self.response_error(str(e))
    

class ServiceFilter(filters.FilterSet):
    business_id = filters.UUIDFilter(field_name='business_id')
    category_id = filters.NumberFilter(field_name='category_id')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    description = filters.CharFilter(field_name='description', lookup_expr='icontains')
    is_active = filters.BooleanFilter(field_name='is_active')
    class Meta:
        model = Service
        fields = ['business_id', 'category_id', 'name', 'description', 'is_active']

class ServiceViewSet(BaseModelViewSet):
    """ViewSet for Service management"""
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [AllowAny]
    filterset_class = ServiceFilter
    
    def get_queryset(self):
        """Get queryset for services"""
        queryset = super().get_queryset().filter(is_active=True)
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create a service"""
        try:
            business_id = request.query_params.get('business_id')
            serializer = ServiceCreateUpdateSerializer(data=request.data, context={'business_id': business_id}) 
            serializer.is_valid(raise_exception=True)
            created_service = serializer.save()
            return self.response_success(ServiceSerializer(created_service).data)
        except Exception as e:
            return self.response_error(str(e))
    
    def destroy(self, request, *args, **kwargs):
        """Destroy a service"""
        try:
            instance = self.get_object()
            instance.is_active = False
            instance.save()
            return self.response_success(data=None, message="Service deleted successfully")
        except Exception as e:
            return self.response_error(str(e))