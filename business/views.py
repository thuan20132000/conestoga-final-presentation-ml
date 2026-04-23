from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import timedelta
from .models import (
    BusinessType, Business, OperatingHours, BusinessSettings, BusinessOnlineBooking,
    BusinessFeedback,
)
from receptionist.models import AIConfigurationStatus
from .serializers import (
    BusinessTypeSerializer,
    BusinessListSerializer,
    OperatingHoursSerializer,
    ReceptionistStatisticsSerializer,
    BusinessDashboardSerializer,
    BusinessSerializer,
    BusinessSettingsSerializer,
    BusinessRolesSerializer,
    BusinessOnlineBookingSerializer,
    BusinessRegisterSerializer,
    GoogleBusinessRegisterSerializer,
    GoogleLoginSerializer,
    FacebookBusinessRegisterSerializer,
    FacebookLoginSerializer,
    BusinessManagementSerializer,
    BusinessFeedbackSerializer,
)
from appointment.serializers import AppointmentDetailSerializer
from payment.serializers import PaymentSerializer
from receptionist.serializers import CallSessionSerializer
from receptionist.serializers import AIConfigurationSerializer
from receptionist.serializers import BusinessStatisticsSerializer
from main.viewsets import BaseModelViewSet, BaseAPIView
from service.serializers import ServiceCategorySerializer, ServiceSerializer, ServiceCategoryWithServicesSerializer
from staff.serializers import StaffSerializer, UserProfileSerializer
from client.serializers import ClientSerializer
from payment.serializers import PaymentMethodSerializer
from payment.services import PaymentService
from staff.permissions import IsBusinessManager, IsBusinessManagerOrReceptionist
from .services import BusinessRegisterService, BusinessGoogleAuthService, BusinessFacebookAuthService, DashboardService, BusinessKnowledgeService
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils.translation import gettext as _
from django.db import transaction
import logging
logger = logging.getLogger(__name__)


class BusinessTypeViewSet(BaseModelViewSet):
    """ViewSet for BusinessType - read-only since these are predefined"""
    queryset = BusinessType.objects.all()
    serializer_class = BusinessTypeSerializer
    permission_classes = [IsAuthenticated, IsBusinessManagerOrReceptionist]


class BusinessViewSet(BaseModelViewSet):
    """ViewSet for Business management"""
    queryset = Business.objects.all()
    permission_classes = [IsAuthenticated, IsBusinessManagerOrReceptionist]

    def get_serializer_class(self):
        if self.action == 'list':
            return BusinessListSerializer
        return BusinessSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        return queryset

    def _trigger_reindex(self, business, reason: str, source_types=None):
        try:
            service = BusinessKnowledgeService(business)
            return service.reindex(reason=reason, source_types=source_types)
        except Exception as exc:
            logger.warning(
                "Business knowledge reindex failed for business=%s reason=%s error=%s",
                business.id,
                reason,
                str(exc),
            )
            return {"error": str(exc)}

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        business = self.get_object()
        transaction.on_commit(
            lambda: self._trigger_reindex(
                business,
                reason="business_updated",
                source_types=["business", "hours", "policy", "ai_prompt"],
            )
        )
        return response

    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        business = self.get_object()
        transaction.on_commit(
            lambda: self._trigger_reindex(
                business,
                reason="business_partially_updated",
                source_types=["business", "hours", "policy", "ai_prompt"],
            )
        )
        return response

    @action(detail=True, methods=['get'], url_path='operating-hours')
    def operating_hours(self, request, pk=None):
        """Get operating hours for a specific business"""
        business = self.get_object()
        hours = business.operating_hours.all()
        serializer = OperatingHoursSerializer(hours, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='business-settings')
    def business_settings(self, request, pk=None):
        """Get settings for a specific business"""
        try:
            business = self.get_object()
            settings = business.settings
            serializer = BusinessSettingsSerializer(settings)
            return self.response_success(serializer.data)
        except Exception as e:
            return self.response_error({'error': str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get statistics for a specific business."""
        business = self.get_object()

        # Get call statistics
        calls = business.calls.all()
        total_calls = calls.count()
        completed_calls = calls.filter(status='completed').count()
        failed_calls = calls.filter(status='failed').count()
        in_progress_calls = calls.filter(status='in_progress').count()

        # Calculate durations
        completed_call_durations = calls.filter(
            status='completed').values_list('duration_seconds', flat=True)
        average_duration = sum(completed_call_durations) / \
            len(completed_call_durations) if completed_call_durations else 0
        total_duration = sum(completed_call_durations)

        # Recent activity (last 7 days)
        week_ago = timezone.now() - timedelta(days=7)
        recent_calls = calls.filter(
            started_at__gte=week_ago).order_by('-started_at')[:10]

        stats_data = {
            'business': business,
            'total_calls': total_calls,
            'completed_calls': completed_calls,
            'failed_calls': failed_calls,
            'average_duration': round(average_duration, 2),
            'total_duration': total_duration,
            'recent_activity': CallSessionSerializer(recent_calls, many=True).data
        }

        serializer = BusinessStatisticsSerializer(stats_data)
        return self.response_success(serializer.data)

    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get analytics for all businesses."""
        businesses = self.get_queryset()
        analytics_data = []

        for business in businesses:
            calls = business.calls.all()
            total_calls = calls.count()
            completed_calls = calls.filter(status='completed').count()

            # Calculate average duration
            completed_call_durations = calls.filter(
                status='completed').values_list('duration_seconds', flat=True)
            average_duration = sum(completed_call_durations) / len(
                completed_call_durations) if completed_call_durations else 0

            analytics_data.append({
                'business': business,
                'total_calls': total_calls,
                'completed_calls': completed_calls,
                'average_duration': round(average_duration, 2)
            })

        serializer = BusinessStatisticsSerializer(analytics_data, many=True)
        return self.response_success(serializer.data)

    @action(detail=True, methods=['get'], url_path='ai-configs')
    def ai_configs(self, request, pk=None):
        """Get health status."""
        object = self.get_object()
        print("Object:: ", object)
        ai_configurations = object.ai_configs
        serializer = AIConfigurationSerializer(ai_configurations, many=True)
        return self.response_success(serializer.data)

    @action(detail=True, methods=['get'], url_path='calls')
    def calls(self, request, pk=None):
        """Get all calls for a business."""
        object = self.get_object()
        params = request.query_params
        from_date = params.get('started_at_from')
        to_date = params.get('started_at_to')
        if from_date and to_date:
            business_calls = object.calls.filter(
                started_at__range=(from_date, to_date)
            )
        else:
            business_calls = object.calls.all()
        
        active_ai_config = object.ai_configs.filter(status=AIConfigurationStatus.ACTIVE.value).first()
        
        serializer = CallSessionSerializer(business_calls, many=True)
        metadata = {
            'ai_configuration': AIConfigurationSerializer(active_ai_config).data if active_ai_config else None
        }
        return self.response_success(serializer.data, metadata=metadata)

    @action(detail=True, methods=['get'], url_path='receptionist-statistics')
    def receptionist_statistics(self, request, pk=None):
        """Get receptionist statistics for a business."""
        try:
            params = request.query_params
            object = self.get_object()
            from_date = params.get('started_at_from')
            to_date = params.get('started_at_to')
            if from_date and to_date:
                business_calls = object.calls.filter(
                    started_at__range=(from_date, to_date)
                )
            else:
                business_calls = object.calls.all()
            serializer = ReceptionistStatisticsSerializer(business_calls)
            return self.response_success(serializer.data)
        except Exception as e:
            return self.response_error({'error': str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(detail=True, methods=['get'], url_path='dashboard')
    def dashboard(self, request, pk=None):
        """Get dashboard KPI metrics for a business."""
        try:
            from datetime import date
            import calendar as cal

            from_date_str = request.query_params.get('from_date')
            to_date_str = request.query_params.get('to_date')

            if from_date_str and to_date_str:
                from_date = date.fromisoformat(from_date_str)
                to_date = date.fromisoformat(to_date_str)
            else:
                today = date.today()
                from_date = today.replace(day=1)
                last_day = cal.monthrange(today.year, today.month)[1]
                to_date = today.replace(day=last_day)

            business = self.get_object()
            service = DashboardService(business, from_date, to_date)
            data = service.get_dashboard_data()
            serializer = BusinessDashboardSerializer(data)
            return self.response_success(serializer.data)
        except ValueError as e:
            return self.response_error({'error': str(e)}, status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return self.response_error({'error': str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='reindex-knowledge')
    def reindex_knowledge(self, request, pk=None):
        """Rebuild business knowledge chunks used by receptionist RAG."""
        business = self.get_object()
        reason = request.data.get("reason", "manual")
        source_types = request.data.get("source_types", ["business", "service", "service_category", "staff", "policy", "hours", "banner", "ai_prompt"])
        if source_types is not None and not isinstance(source_types, list):
            return self.response_error(
                data={"source_types": "Must be a list of source types."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = BusinessKnowledgeService(business).reindex(reason=reason, source_types=source_types)
            logger.info("Knowledge reindex success business=%s reason=%s result=%s", business.id, reason, result)
            return self.response_success(result, message="Knowledge reindex completed")
        except Exception as exc:
            logger.exception("Knowledge reindex failed for business=%s", business.id)
            return self.response_error(
                data={"error": str(exc)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=['post'], url_path='search-knowledge')
    def search_knowledge(self, request, pk=None):
        """Semantic search over per-business knowledge chunks."""
        business = self.get_object()
        query = request.data.get("query")
        if not query:
            return self.response_error(
                data={"query": "This field is required."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        top_k = int(request.data.get("top_k", 5))
        top_k = max(1, min(top_k, 10))
        source_types = request.data.get("source_types")
        if source_types is not None and not isinstance(source_types, list):
            return self.response_error(
                data={"source_types": "Must be a list of source types."},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        score_threshold = request.data.get("score_threshold")
        if score_threshold is not None:
            score_threshold = float(score_threshold)

        try:
            results = BusinessKnowledgeService(business).search(
                query=query,
                top_k=top_k,
                source_types=source_types,
                score_threshold=score_threshold,
            )
            return self.response_success(results)
        except Exception as exc:
            logger.exception("Knowledge search failed for business=%s", business.id)
            return self.response_error(
                data={"error": str(exc)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=['get'], url_path='management')
    def management(self, request, pk=None):
        """Get management data for a business."""
        try:
            object = self.get_object()
            serializer = BusinessManagementSerializer(object)
            return self.response_success(serializer.data)
        except Exception as e:
            return self.response_error({'error': str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    
    @action(detail=True, methods=['get'], url_path='service-categories')
    def service_categories(self, request, pk=None):
        """Get services categories for a business."""
        object = self.get_object()
        categories = object.service_categories.filter(is_active=True)
        serializer = ServiceCategorySerializer(categories, many=True)
        return self.response_success(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='services')
    def services(self, request, pk=None):
        """Get services for a business."""
        object = self.get_object()
        services = object.services.filter(is_active=True)
        serializer = ServiceSerializer(services, many=True)
        return self.response_success(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='categories-services')
    def categories_services(self, request, pk=None):
        """Get services for all categories of a business."""
        object = self.get_object()
        categories = object.service_categories.filter(is_active=True)
        serializer = ServiceCategoryWithServicesSerializer(categories, many=True)
        return self.response_success(serializer.data)

    @action(detail=True, methods=['get'], url_path='staff')
    def staff(self, request, pk=None):
        """Get staff for a business."""
        object = self.get_object()
        staff = object.staff.filter(is_deleted=False, is_active=True)
        serializer = StaffSerializer(staff, many=True)
        return self.response_success(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='roles')
    def roles(self, request, pk=None):
        """Get roles for a business."""
        object = self.get_object()
        roles = object.roles.all()
        serializer = BusinessRolesSerializer(roles, many=True)
        return self.response_success(serializer.data)

    @action(detail=True, methods=['get'], url_path='clients')
    def clients(self, request, pk=None):
        """Get clients for a business."""
        object = self.get_object()
        clients = object.primary_clients.filter(is_active=True).order_by('-created_at')
        serializer = ClientSerializer(clients, many=True)
        return self.response_success(serializer.data)

    @action(detail=True, methods=['get'], url_path='appointments')
    def appointments(self, request, pk=None):   
        """Get appointments for a business."""
        object = self.get_object()
        appointments = object.appointments.all()
        serializer = AppointmentDetailSerializer(appointments, many=True)
        return self.response_success(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='payment-methods')
    def payment_methods(self, request, pk=None):
        """Get payment methods for a business."""
        object = self.get_object()
        payment_methods = object.payment_methods.all()
        serializer = PaymentMethodSerializer(payment_methods, many=True)
        return self.response_success(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='payments-stats')
    def payment_stats(self, request, pk=None):
        """Get payment stats for a business."""
        try:
            object = self.get_object()
            
            from_date = request.query_params.get('from_date')
            to_date = request.query_params.get('to_date')
            
            payment_service = PaymentService()
            payment_stats = payment_service.get_payment_stats(object, from_date, to_date)
            serializer = PaymentSerializer(payment_stats['results'], many=True)
            metadata = payment_stats['metadata']
            return self.response_success(serializer.data, metadata=metadata)
        except Exception as e:
            return self.response_error({'error': str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

class OperatingHoursViewSet(BaseModelViewSet):
    """ViewSet for OperatingHours management"""
    queryset = OperatingHours.objects.select_related('business')
    serializer_class = OperatingHoursSerializer
    permission_classes = [IsAuthenticated, IsBusinessManager]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['business', 'day_of_week', 'is_open']
    ordering_fields = ['day_of_week']
    ordering = ['day_of_week']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by business if specified
        business_id = self.request.query_params.get('business')
        if business_id:
            queryset = queryset.filter(business_id=business_id)

        return queryset

    def perform_update(self, serializer):
        instance = serializer.save(business=self.get_object().business)
        transaction.on_commit(
            lambda: BusinessKnowledgeService(instance.business).reindex(
                reason="operating_hours_updated",
                source_types=["hours"],
            )
        )

class BusinessSettingsViewSet(BaseModelViewSet):
    """ViewSet for BusinessSettings management"""
    queryset = BusinessSettings.objects.all()
    serializer_class = BusinessSettingsSerializer
    permission_classes = [IsAuthenticated, IsBusinessManagerOrReceptionist]

    def perform_update(self, serializer):
        instance = serializer.save(business=self.get_object().business)
        transaction.on_commit(
            lambda: BusinessKnowledgeService(instance.business).reindex(
                reason="business_settings_updated",
                source_types=["business", "policy"],
            )
        )

class BusinessOnlineBookingViewSet(BaseModelViewSet):
    """ViewSet for BusinessOnlineBooking management"""
    queryset = BusinessOnlineBooking.objects.all()
    serializer_class = BusinessOnlineBookingSerializer
    permission_classes = [IsAuthenticated, IsBusinessManagerOrReceptionist]

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(business=self.request.user.business)

    def perform_update(self, serializer):
        instance = serializer.save(business=self.get_object().business)
        transaction.on_commit(
            lambda: BusinessKnowledgeService(instance.business).reindex(
                reason="business_online_booking_updated",
                source_types=["policy", "banner"],
            )
        )


class BusinessRegisterView(BaseAPIView):
    """
    Public endpoint to register a new business and its initial owner.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            serializer = BusinessRegisterSerializer(data=request.data)
            if serializer.is_valid():
                business_data = serializer.validated_data['business']
                owner_data = serializer.validated_data['owner']
                business_type_name = serializer.validated_data['business']['business_type']
                settings_data = serializer.validated_data['settings']
                business_service = BusinessRegisterService(business_data, owner_data, business_type_name, settings_data)
                owner = business_service.initialize()
                
                user_serializer = UserProfileSerializer(owner)
                refresh = RefreshToken.for_user(owner)
                
                return Response({
                    'success': True,
                    'message': _('Registration successful'),
                    'results': {
                        'user': user_serializer.data,
                        'tokens': {
                            'refresh': str(refresh),
                            'access': str(refresh.access_token),
                        }
                    }
                }, status=status.HTTP_201_CREATED)

            return Response({
                'success': False,
                'message': _('Registration failed'),
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as exc:
            
            return Response({
                'success': False,
                'message': _('Error during registration'),
                'error': str(exc)
            }, status=status.HTTP_400_BAD_REQUEST)


class BusinessGoogleRegisterView(BaseAPIView):
    """
    Public endpoint to register a new business and owner via Google OAuth.
    POST /api/business/auth/google/register/
    """

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            serializer = GoogleBusinessRegisterSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'success': False,
                    'message': _('Registration failed'),
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

            google_id_token = serializer.validated_data['google_id_token']
            business_data = serializer.validated_data['business']
            business_type_name = business_data.get('business_type')
            settings_data = serializer.validated_data['settings']

            owner = BusinessGoogleAuthService.register(
                google_id_token=google_id_token,
                business_data=business_data,
                business_type_name=business_type_name,
                settings_data=settings_data,
            )

            user_serializer = UserProfileSerializer(owner)
            refresh = RefreshToken.for_user(owner)

            return Response({
                'success': True,
                'message': _('Registration successful'),
                'results': {
                    'user': user_serializer.data,
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }
            }, status=status.HTTP_201_CREATED)

        except ValueError as exc:
            return Response({
                'success': False,
                'message': str(exc),
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as exc:
            return Response({
                'success': False,
                'message': _('Error during registration'),
                'error': str(exc)
            }, status=status.HTTP_400_BAD_REQUEST)


class BusinessGoogleLoginView(BaseAPIView):
    """
    Public endpoint for business owner login via Google OAuth.
    POST /api/business/auth/google/login/
    """

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            serializer = GoogleLoginSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'success': False,
                    'message': _('Login failed'),
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

            google_id_token = serializer.validated_data['google_id_token']
            owner = BusinessGoogleAuthService.login(google_id_token=google_id_token)
            user_serializer = UserProfileSerializer(owner)
            refresh = RefreshToken.for_user(owner)
            return Response({
                'success': True,
                'message': _('Login successful'),
                'results': {
                    'user': user_serializer.data,
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }
            }, status=status.HTTP_200_OK)

        except ValueError as exc:
            return Response({
                'success': False,
                'message': str(exc),
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as exc:
            return Response({
                'success': False,
                'message': _('Error during login'),
                'error': str(exc)
            }, status=status.HTTP_400_BAD_REQUEST)


class BusinessFacebookRegisterView(BaseAPIView):
    """
    Public endpoint to register a new business and owner via Facebook OAuth.
    POST /api/business/auth/facebook/register/
    """

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            serializer = FacebookBusinessRegisterSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'success': False,
                    'message': _('Registration failed'),
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

            facebook_access_token = serializer.validated_data['facebook_access_token']
            business_data = serializer.validated_data['business']
            business_type_name = business_data.get('business_type')
            settings_data = serializer.validated_data['settings']

            owner = BusinessFacebookAuthService.register(
                facebook_access_token=facebook_access_token,
                business_data=business_data,
                business_type_name=business_type_name,
                settings_data=settings_data,
            )

            user_serializer = UserProfileSerializer(owner)
            refresh = RefreshToken.for_user(owner)

            return Response({
                'success': True,
                'message': _('Registration successful'),
                'results': {
                    'user': user_serializer.data,
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }
            }, status=status.HTTP_201_CREATED)

        except ValueError as exc:
            return Response({
                'success': False,
                'message': str(exc),
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as exc:
            return Response({
                'success': False,
                'message': _('Error during registration'),
                'error': str(exc)
            }, status=status.HTTP_400_BAD_REQUEST)


class BusinessFacebookLoginView(BaseAPIView):
    """
    Public endpoint for business owner login via Facebook OAuth.
    POST /api/business/auth/facebook/login/
    """

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            serializer = FacebookLoginSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'success': False,
                    'message': _('Login failed'),
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

            facebook_access_token = serializer.validated_data['facebook_access_token']
            owner = BusinessFacebookAuthService.login(facebook_access_token=facebook_access_token)
            user_serializer = UserProfileSerializer(owner)
            refresh = RefreshToken.for_user(owner)
            return Response({
                'success': True,
                'message': _('Login successful'),
                'results': {
                    'user': user_serializer.data,
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }
            }, status=status.HTTP_200_OK)

        except ValueError as exc:
            return Response({
                'success': False,
                'message': str(exc),
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as exc:
            return Response({
                'success': False,
                'message': _('Error during login'),
                'error': str(exc)
            }, status=status.HTTP_400_BAD_REQUEST)


class BusinessFeedbackViewSet(BaseModelViewSet):
    """ViewSet for business feedback to the platform."""
    queryset = BusinessFeedback.objects.select_related('business', 'submitted_by').all()
    serializer_class = BusinessFeedbackSerializer
    permission_classes = [IsAuthenticated, IsBusinessManager]

    def get_queryset(self):
        return super().get_queryset().filter(
            business=self.request.user.business
        )

    def perform_create(self, serializer):
        feedback = serializer.save(
            business=self.request.user.business,
            submitted_by=self.request.user,
        )
        self._send_confirmation_email(feedback)

    def _send_confirmation_email(self, feedback):
        user = feedback.submitted_by
        email = user.email
        if not email:
            return
        from notifications.services import EmailService
        EmailService().send_async(
            subject=f"Thanks for your feedback – {feedback.subject}",
            to_email=email,
            template='emails/feedback_confirmation.html',
            context={
                'submitted_by_name': user.get_full_name() or user.username,
                'business_name': feedback.business.name,
                'category': feedback.get_category_display(),
                'subject': feedback.subject,
                'message': feedback.message,
            },
        )