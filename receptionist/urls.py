from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets import (
    AIConfigurationViewSet, CallSessionViewSet,
    ConversationMessageViewSet, IntentViewSet, AudioRecordingViewSet,
    SystemLogViewSet
)
from . import views

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'ai-configurations', AIConfigurationViewSet, basename='aiconfiguration')
router.register(r'calls', CallSessionViewSet, basename='call')
router.register(r'conversations', ConversationMessageViewSet, basename='message')
router.register(r'intents', IntentViewSet, basename='intent')
router.register(r'recordings', AudioRecordingViewSet, basename='recording')
router.register(r'logs', SystemLogViewSet, basename='log')

# API URL patterns
urlpatterns = [
    # API root
    path('', views.api_root, name='api_root'),
    
    # Router URLs
    path('', include(router.urls)),
    
    # Custom API endpoints
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('analytics/', views.AnalyticsView.as_view(), name='analytics'),
    path('health/', views.HealthCheckView.as_view(), name='health_check'),
    
    # Webhook endpoints
    path('webhooks/twilio/', views.TwilioWebhookView.as_view(), name='twilio_webhook'),
    
    # Export endpoints
    path('export/calls/', views.ExportCallsView.as_view(), name='export_calls'),
    path('export/statistics/', views.ExportStatisticsView.as_view(), name='export_statistics'),
]
