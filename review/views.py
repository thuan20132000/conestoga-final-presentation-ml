from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Avg, F
from django.utils import timezone
from datetime import timedelta
from django_filters import rest_framework as filters
from django.db import transaction

from .models import Review
from .serializers import (
    ReviewSerializer,
    ReviewCreateSerializer,
    ReviewListSerializer,
    ReviewDetailSerializer,
    ReviewStatsSerializer
)
from main.viewsets import BaseModelViewSet
from appointment.models import Appointment


class ReviewFilter(filters.FilterSet):
    """Filter for Review model"""
    appointment_id = filters.NumberFilter(field_name='appointment_id')
    business_id = filters.UUIDFilter(field_name='appointment__business_id')
    rating = filters.NumberFilter(field_name='rating')
    min_rating = filters.NumberFilter(field_name='rating', lookup_expr='gte')
    max_rating = filters.NumberFilter(field_name='rating', lookup_expr='lte')
    is_visible = filters.BooleanFilter(field_name='is_visible')
    is_verified = filters.BooleanFilter(field_name='is_verified')
    is_active = filters.BooleanFilter(field_name='is_active')
    reviewed_date = filters.DateFilter(field_name='reviewed_at', lookup_expr='date', required=True)
    
    class Meta:
        model = Review
        fields = [
            'appointment_id',
            'business_id',
            'rating',
            'min_rating',
            'max_rating',
            'is_visible',
            'is_verified',
            'is_active',
            'reviewed_date'
        ]


class ReviewViewSet(BaseModelViewSet):
    """ViewSet for managing reviews"""
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = ReviewFilter
    ordering_fields = ['reviewed_at', 'rating', 'created_at']
    ordering = ['-reviewed_at', '-created_at']
    # permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return ReviewCreateSerializer
        if self.action == 'list':
            return ReviewListSerializer
        if self.action == 'retrieve':
            return ReviewDetailSerializer
        return ReviewSerializer
    
    def get_queryset(self):
        """Get queryset for reviews"""
        queryset = super().get_queryset()
        queryset = queryset.filter(is_deleted=False)
        
        # Filter by business if business_id is provided
        business_id = self.request.query_params.get('business_id')
        if business_id:
            queryset = queryset.filter(appointment__business_id=business_id)
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """List reviews"""
        queryset = self.get_queryset()
        queryset = self.filter_queryset(queryset)
        
        # By default, only show visible reviews for non-authenticated users
        # For authenticated users, show all reviews
        if not request.user.is_authenticated:
            queryset = queryset.filter(is_visible=True, is_active=True)
        
        serializer = self.get_serializer(queryset, many=True)
        return self.response_success(serializer.data)
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a review"""
        instance = self.get_object()
        
        # Check if review is visible for non-authenticated users
        if not request.user.is_authenticated and not instance.is_visible:
            return self.response_error(
                {'error': 'Review not found'},
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(instance)
        return self.response_success(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """Create a review"""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            print("serializer.validated_data", serializer.validated_data)
            appointment_id = serializer.validated_data.get('appointment').id
            appointment = Appointment.objects.get(id=appointment_id)
            review = serializer.save()
            return self.response_success(
                ReviewDetailSerializer(review).data,
                status_code=status.HTTP_201_CREATED,
                message="Review created successfully"
            )
        except Exception as e:
            return self.response_error(str(e))
    
    def partial_update(self, request, *args, **kwargs):
        """Partial update a review"""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            review = serializer.save()
            return self.response_success(
                ReviewDetailSerializer(review).data,
                message="Review updated successfully"
            )
        except Exception as e:
            return self.response_error(str(e))
    
    def destroy(self, request, *args, **kwargs):
        """Soft delete a review"""
        try:
            instance = self.get_object()
            instance.soft_delete()
            return self.response_success(
                ReviewSerializer(instance).data,
                message="Review deleted successfully"
            )
        except Exception as e:
            return self.response_error(str(e))
    
    @action(detail=False, methods=['get'], url_path='by-appointment/(?P<appointment_id>[^/.]+)')
    def by_appointment(self, request, appointment_id=None):
        """Get reviews for a specific appointment"""
        try:
            reviews = self.get_queryset().filter(appointment_id=appointment_id)
            
            # Filter visible reviews for non-authenticated users
            if not request.user.is_authenticated:
                reviews = reviews.filter(is_visible=True, is_active=True)
            
            serializer = ReviewListSerializer(reviews, many=True)
            return self.response_success(serializer.data)
        except Exception as e:
            return self.response_error(str(e))
    
    
    @action(detail=False, methods=['get'], url_path='by-business/(?P<business_id>[^/.]+)')
    def by_business(self, request, business_id=None):
        """Get reviews for a specific business"""
        try:
            reviews = self.get_queryset().filter(appointment__business_id=business_id)
            
            # Filter visible reviews for non-authenticated users
            if not request.user.is_authenticated:
                reviews = reviews.filter(is_visible=True, is_active=True)
            
            serializer = ReviewListSerializer(reviews, many=True)
            return self.response_success(serializer.data)
        except Exception as e:
            return self.response_error(str(e))
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get review statistics"""
        try:
            business_id = request.query_params.get('business_id')
            queryset = self.get_queryset()
            
            if business_id:
                queryset = queryset.filter(appointment__business_id=business_id)
            
            # Only count visible reviews for stats
            visible_queryset = queryset.filter(is_visible=True, is_active=True)
            
            total_reviews = visible_queryset.count()
            average_rating = visible_queryset.aggregate(
                avg_rating=Avg('rating')
            )['avg_rating'] or 0.0
            
            # Rating distribution
            rating_distribution = {}
            for rating in range(1, 6):
                count = visible_queryset.filter(rating=rating).count()
                rating_distribution[str(rating)] = count
            
            verified_reviews = visible_queryset.filter(is_verified=True).count()
            visible_reviews = visible_queryset.filter(is_visible=True).count()
            
            # Recent reviews (last 7 days)
            seven_days_ago = timezone.now() - timedelta(days=7)
            recent_reviews = visible_queryset.filter(reviewed_at__gte=seven_days_ago).count()
            
            stats_data = {
                'total_reviews': total_reviews,
                'average_rating': round(average_rating, 2),
                'rating_distribution': rating_distribution,
                'verified_reviews': verified_reviews,
                'visible_reviews': visible_reviews,
                'recent_reviews': recent_reviews
            }
            
            serializer = ReviewStatsSerializer(stats_data)
            return self.response_success(serializer.data)
        except Exception as e:
            return self.response_error(str(e))
    
    @action(detail=True, methods=['post'], url_path='toggle-visibility')
    def toggle_visibility(self, request, pk=None):
        """Toggle review visibility"""
        try:
            review = self.get_object()
            review.is_visible = not review.is_visible
            review.save()
            return self.response_success(
                ReviewDetailSerializer(review).data,
                message=f"Review visibility set to {review.is_visible}"
            )
        except Exception as e:
            return self.response_error(str(e))

class BusinessReviewViewSet(BaseModelViewSet):
    """ViewSet for managing business reviews"""
    queryset = Review.objects.filter(is_deleted=False)
    serializer_class = ReviewSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = ReviewFilter
    ordering_fields = ['reviewed_at', 'rating', 'created_at']
    ordering = ['-reviewed_at', '-created_at']
    # permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return ReviewCreateSerializer
        if self.action == 'list':
            return ReviewListSerializer
        if self.action == 'retrieve':
            return ReviewDetailSerializer
        return ReviewSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a review"""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            review = serializer.save()
            return self.response_success(
                ReviewDetailSerializer(review).data,
                status_code=status.HTTP_201_CREATED,
                message="Review created successfully"
            )
        except Exception as e:
            return self.response_error(str(e))

    
    @action(detail=False, methods=['get'], url_path='by-business/(?P<business_id>[^/.]+)')
    def by_business(self, request, business_id=None):
        """Get reviews for a specific business"""
        try:
            reviews = self.get_queryset().filter(appointment__business_id=business_id)
            serializer = ReviewListSerializer(reviews, many=True)
            return self.response_success(serializer.data)
        except Exception as e:
            return self.response_error(str(e))
        
    
    @action(detail=False, methods=['get'],url_path='appointment/(?P<appointment_id>[^/.]+)')
    def appointment_review(self, request, appointment_id=None):
        """Get reviews for a specific appointment"""
        try:
            print("appointment_id", appointment_id)
            reviews = self.queryset.filter(appointment_id=appointment_id).first()
            print("reviews", reviews)
            if not reviews:
                return self.response_error("Review not found", status_code=status.HTTP_404_NOT_FOUND)
            serializer = ReviewDetailSerializer(reviews)
            return self.response_success(serializer.data)
        except Exception as e:
            return self.response_error(str(e))