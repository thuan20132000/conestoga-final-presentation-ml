from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BusinessTypeViewSet,
    BusinessViewSet,
    OperatingHoursViewSet,
    BusinessSettingsViewSet,
    BusinessOnlineBookingViewSet,
    BusinessRegisterView,
    BusinessGoogleRegisterView,
    BusinessGoogleLoginView,
    BusinessFacebookRegisterView,
    BusinessFacebookLoginView,
    BusinessFeedbackViewSet,
)

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'business', BusinessViewSet, basename='business')
router.register(r'business-type', BusinessTypeViewSet, basename='business-type')
router.register(r'operating-hours', OperatingHoursViewSet, basename='operating-hours')
router.register(r'business-settings', BusinessSettingsViewSet, basename='business-settings')
router.register(r'business-online-booking', BusinessOnlineBookingViewSet, basename='business-online-booking')
router.register(r'business-feedback', BusinessFeedbackViewSet, basename='business-feedback')

# The API URLs are now determined automatically by the router
urlpatterns = [
    path('', include(router.urls)),
    path('business/auth/register/', BusinessRegisterView.as_view(), name='business-register'),
    path('business/auth/google/register/', BusinessGoogleRegisterView.as_view(), name='business-google-register'),
    path('business/auth/google/login/', BusinessGoogleLoginView.as_view(), name='business-google-login'),
    path('business/auth/facebook/register/', BusinessFacebookRegisterView.as_view(), name='business-facebook-register'),
    path('business/auth/facebook/login/', BusinessFacebookLoginView.as_view(), name='business-facebook-login'),
]
