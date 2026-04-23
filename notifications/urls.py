from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import NotificationViewSet, PushDeviceViewSet, SMSNotificationViewSet, PushNotificationViewSet
from .views import WebPushViewSet

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"sms-notifications", SMSNotificationViewSet, basename="sms-notification")  
router.register(r"push-notifications", PushNotificationViewSet, basename="push-notification")
router.register(r"push-devices", PushDeviceViewSet, basename="pushdevice")
router.register(r"webpush", WebPushViewSet, basename="webpush")

urlpatterns = [
    path("", include(router.urls)),
]
