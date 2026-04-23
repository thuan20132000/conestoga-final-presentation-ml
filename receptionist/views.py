from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .permissions import AnalyticsPermission, ExportPermission, WebhookPermission
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Count, Q, Avg
from datetime import datetime, timedelta
import json
import csv

from .models import (
    CallSession, ConversationMessage, Intent, 
    AudioRecording, SystemLog
)
from .serializers import (
    CallSessionSerializer, IntentSerializer,
    APIResponseSerializer
)
from business.serializers import BusinessDetailSerializer
from business.models import Business


class DashboardView(APIView):
    """Dashboard view with overview statistics."""
    
    # permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get dashboard statistics."""
        try:
            # Get basic counts
            total_businesses = Business.objects.all().count()
            total_calls = CallSession.objects.count()
            active_calls = CallSession.objects.filter(status='in_progress').count()
            completed_calls = CallSession.objects.filter(status='completed').count()
            
            # Recent activity (last 24 hours)
            yesterday = timezone.now() - timedelta(days=1)
            recent_calls = CallSession.objects.filter(started_at__gte=yesterday).count()
            
            # Top businesses by call volume
            top_businesses = Business.objects.all().annotate(
                call_count=Count('calls')
            ).order_by('-call_count')[:5]
            
            # Recent calls
            recent_call_sessions = CallSession.objects.order_by('-started_at')[:10]
            
            # Intent statistics
            intent_stats = Intent.objects.values('name').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            dashboard_data = {
                'overview': {
                    'total_businesses': total_businesses,
                    'total_calls': total_calls,
                    'active_calls': active_calls,
                    'completed_calls': completed_calls,
                    'recent_calls_24h': recent_calls
                },
                'top_businesses': BusinessDetailSerializer(top_businesses, many=True).data,
                'recent_calls': CallSessionSerializer(recent_call_sessions, many=True).data,
                'top_intents': list(intent_stats)
            }
            
            response_data = {
                'success': True,
                'message': 'Dashboard data retrieved successfully',
                'data': dashboard_data
            }
            
            return Response(response_data)
            
        except Exception as e:
            response_data = {
                'success': False,
                'message': f'Error retrieving dashboard data: {str(e)}',
                'data': None
            }
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AnalyticsView(APIView):
    """Analytics view with detailed statistics."""
    
    permission_classes = [AnalyticsPermission]
    
    def get(self, request):
        """Get analytics data."""
        try:
            # Get time range from query params
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timedelta(days=days)
            
            # Call statistics
            calls_in_period = CallSession.objects.filter(started_at__gte=start_date)
            
            total_calls = calls_in_period.count()
            completed_calls = calls_in_period.filter(status='completed').count()
            failed_calls = calls_in_period.filter(status='failed').count()
            
            # Average duration
            avg_duration = calls_in_period.filter(
                status='completed'
            ).aggregate(avg_duration=Avg('duration_seconds'))['avg_duration'] or 0
            
            # Calls by day
            calls_by_day = {}
            for i in range(days):
                date = timezone.now() - timedelta(days=i)
                day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + timedelta(days=1)
                day_calls = calls_in_period.filter(
                    started_at__gte=day_start, 
                    started_at__lt=day_end
                ).count()
                calls_by_day[day_start.strftime('%Y-%m-%d')] = day_calls
            
            # Business performance
            business_stats = Business.objects.all().annotate(
                total_calls=Count('calls', filter=Q(calls__started_at__gte=start_date)),
                completed_calls=Count('calls', filter=Q(
                    calls__started_at__gte=start_date,
                    calls__status='completed'
                )),
                avg_duration=Avg('calls__duration_seconds', filter=Q(
                    calls__started_at__gte=start_date,
                    calls__status='completed'
                ))
            ).filter(total_calls__gt=0).order_by('-total_calls')
            
            # Intent analytics
            intent_analytics = Intent.objects.filter(
                created_at__gte=start_date
            ).values('name').annotate(
                count=Count('id'),
                avg_confidence=Avg('confidence')
            ).order_by('-count')
            
            analytics_data = {
                'period': {
                    'days': days,
                    'start_date': start_date,
                    'end_date': timezone.now()
                },
                'calls': {
                    'total': total_calls,
                    'completed': completed_calls,
                    'failed': failed_calls,
                    'completion_rate': (completed_calls / total_calls * 100) if total_calls > 0 else 0,
                    'average_duration': round(avg_duration, 2),
                    'by_day': calls_by_day
                },
                'businesses': [
                    {
                        'id': business.id,
                        'name': business.name,
                        'total_calls': business.total_calls,
                        'completed_calls': business.completed_calls,
                        'completion_rate': (business.completed_calls / business.total_calls * 100) if business.total_calls > 0 else 0,
                        'average_duration': round(business.avg_duration or 0, 2)
                    }
                    for business in business_stats
                ],
                'intents': list(intent_analytics)
            }
            
            response_data = {
                'success': True,
                'message': 'Analytics data retrieved successfully',
                'data': analytics_data
            }
            
            return Response(response_data)
            
        except Exception as e:
            response_data = {
                'success': False,
                'message': f'Error retrieving analytics data: {str(e)}',
                'data': None
            }
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class HealthCheckView(APIView):
    """Health check endpoint."""
    
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Get system health status."""
        try:
            # Basic health checks
            business_count = Business.objects.all().count()
            call_count = CallSession.objects.count()
            
            # Check for recent errors
            recent_errors = SystemLog.objects.filter(
                level='error',
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            health_data = {
                'status': 'healthy',
                'timestamp': timezone.now().isoformat(),
                'database': 'connected',
                'businesses': business_count,
                'calls': call_count,
                'recent_errors': recent_errors
            }
            
            response_data = {
                'success': True,
                'message': 'System is healthy',
                'data': health_data
            }
            
            return Response(response_data)
            
        except Exception as e:
            response_data = {
                'success': False,
                'message': f'System health check failed: {str(e)}',
                'data': {
                    'status': 'unhealthy',
                    'timestamp': timezone.now().isoformat()
                }
            }
            return Response(response_data, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class TwilioWebhookView(APIView):
    """Webhook endpoint for Twilio callbacks."""
    
    permission_classes = [WebhookPermission]
    
    def post(self, request):
        """Handle Twilio webhook."""
        try:
            data = request.data
            
            # Log the webhook data
            SystemLog.objects.create(
                level='info',
                message='Twilio webhook received',
                metadata=data
            )
            
            # Process different webhook types
            call_sid = data.get('CallSid')
            call_status = data.get('CallStatus')
            
            if call_sid:
                try:
                    call_session = CallSession.objects.get(call_sid=call_sid)
                    
                    # Update call status
                    if call_status in ['completed', 'busy', 'no-answer', 'failed', 'canceled']:
                        call_session.status = 'completed' if call_status == 'completed' else 'failed'
                        call_session.ended_at = timezone.now()
                        
                        # Calculate duration
                        if call_session.started_at and call_session.ended_at:
                            duration = call_session.ended_at - call_session.started_at
                            call_session.duration_seconds = int(duration.total_seconds())
                        
                        call_session.save()
                        
                        SystemLog.objects.create(
                            call=call_session,
                            level='info',
                            message=f'Call status updated to {call_status}',
                            metadata={'twilio_status': call_status}
                        )
                    
                except CallSession.DoesNotExist:
                    SystemLog.objects.create(
                        level='warning',
                        message=f'Call session not found for SID: {call_sid}',
                        metadata={'call_sid': call_sid}
                    )
            
            response_data = {
                'success': True,
                'message': 'Webhook processed successfully'
            }
            
            return Response(response_data)
            
        except Exception as e:
            SystemLog.objects.create(
                level='error',
                message=f'Twilio webhook processing failed: {str(e)}',
                metadata={'error': str(e)}
            )
            
            response_data = {
                'success': False,
                'message': f'Webhook processing failed: {str(e)}'
            }
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ExportCallsView(APIView):
    """Export calls data as CSV."""
    
    # permission_classes = [ExportPermission]
    
    def get(self, request):
        """Export calls data."""
        try:
            # Get query parameters
            business_id = request.query_params.get('business_id')
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            format_type = request.query_params.get('format', 'csv')
            
            # Build queryset
            queryset = CallSession.objects.all()
            
            if business_id:
                queryset = queryset.filter(business_id=business_id)
            
            if start_date:
                queryset = queryset.filter(started_at__gte=start_date)
            
            if end_date:
                queryset = queryset.filter(started_at__lte=end_date)
            
            if format_type == 'csv':
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = 'attachment; filename="calls_export.csv"'
                
                writer = csv.writer(response)
                writer.writerow([
                    'Call SID', 'Business', 'Direction', 'Caller Number',
                    'Receiver Number', 'Started At', 'Ended At', 
                    'Duration (seconds)', 'Status', 'Transcript Summary'
                ])
                
                for call in queryset:
                    writer.writerow([
                        call.call_sid,
                        call.business.name,
                        call.direction,
                        call.caller_number,
                        call.receiver_number,
                        call.started_at,
                        call.ended_at,
                        call.duration_seconds,
                        call.status,
                        call.transcript_summary
                    ])
                
                return response
            
            elif format_type == 'json':
                serializer = CallSessionSerializer(queryset, many=True)
                return JsonResponse({
                    'success': True,
                    'data': serializer.data
                })
            
            else:
                return Response({
                    'success': False,
                    'message': 'Invalid format. Use "csv" or "json".'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Export failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ExportStatisticsView(APIView):
    """Export statistics data."""
    
    permission_classes = [ExportPermission]
    
    def get(self, request):
        """Export statistics data."""
        try:
            # Get time range
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timedelta(days=days)
            
            # Generate statistics
            calls = CallSession.objects.filter(started_at__gte=start_date)
            
            stats_data = {
                'period': {
                    'days': days,
                    'start_date': start_date,
                    'end_date': timezone.now()
                },
                'summary': {
                    'total_calls': calls.count(),
                    'completed_calls': calls.filter(status='completed').count(),
                    'failed_calls': calls.filter(status='failed').count(),
                    'average_duration': calls.filter(
                        status='completed'
                    ).aggregate(avg=Avg('duration_seconds'))['avg'] or 0
                },
                'businesses': [
                    {
                        'name': business.name,
                        'total_calls': business.calls.all().filter(started_at__gte=start_date).count(),
                        'completed_calls': business.calls.filter(
                            started_at__gte=start_date,
                            status='completed'
                        ).count()
                    }
                    for business in Business.objects.all().count()
                ]
            }
            
            return JsonResponse({
                'success': True,
                'data': stats_data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Statistics export failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_root(request):
    """API root endpoint with available endpoints."""
    endpoints = {
        'authentication': {
            'login': '/api/auth/login/',
            'refresh': '/api/auth/refresh/'
        },
        'resources': {
            'business': '/api/business/',
            'ai_configurations': '/api/ai-configurations/',
            'calls': '/api/calls/',
            'messages': '/api/messages/',
            'intents': '/api/intents/',
            'recordings': '/api/recordings/',
            'logs': '/api/logs/'
        },
        'special_endpoints': {
            'dashboard': '/api/dashboard/',
            'analytics': '/api/analytics/',
            'health': '/api/health/',
            'export_calls': '/api/export/calls/',
            'export_statistics': '/api/export/statistics/',
            'twilio_webhook': '/api/webhooks/twilio/'
        }
    }
    
    return Response({
        'success': True,
        'message': 'Receptionist API - Available endpoints',
        'data': endpoints
    })
