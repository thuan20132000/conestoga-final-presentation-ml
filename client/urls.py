from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ClientViewSet,
    ClientRegisterView,
    ClientGoogleLoginView,
    ClientFacebookLoginView,
    ClientRequestOTPView,
    ClientVerifyOTPView,
    ClientRefreshTokenView,
    ClientProfileView,
    ClientAppointmentListView,
    ClientPushSubscribeView,
    ClientPushUnsubscribeView,
)

app_name = "client"

router = DefaultRouter()
router.register(r"clients", ClientViewSet, basename="client")

urlpatterns = [
    path("", include(router.urls)),
    # Client auth (OTP-based, passwordless)
    path(
        "client-auth/register/",
        ClientRegisterView.as_view(),
        name="client-register",
    ),
    path(
        "client-auth/google/",
        ClientGoogleLoginView.as_view(),
        name="client-google-login",
    ),
    path(
        "client-auth/facebook/",
        ClientFacebookLoginView.as_view(),
        name="client-facebook-login",
    ),
    path(
        "client-auth/request-otp/",
        ClientRequestOTPView.as_view(),
        name="client-request-otp",
    ),
    path(
        "client-auth/verify-otp/",
        ClientVerifyOTPView.as_view(),
        name="client-verify-otp",
    ),
    path(
        "client-auth/refresh/",
        ClientRefreshTokenView.as_view(),
        name="client-refresh-token",
    ),
    path("client-auth/me/", ClientProfileView.as_view(), name="client-profile"),
    # Client portal
    path(
        "client-portal/appointments/",
        ClientAppointmentListView.as_view(),
        name="client-appointments",
    ),
    path(
        "client-portal/push-subscribe/",
        ClientPushSubscribeView.as_view(),
        name="client-push-subscribe",
    ),
    path(
        "client-portal/push-unsubscribe/",
        ClientPushUnsubscribeView.as_view(),
        name="client-push-unsubscribe",
    ),
]
