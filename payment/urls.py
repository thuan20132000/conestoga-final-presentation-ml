from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import (
    PaymentViewSet,
    POSPaymentViewSet,
    PaymentMethodViewSet,
)
from .views import StripeConnectOnboardingView, StripeConnectLoginLinkView


# Create router and register viewsets
router = DefaultRouter()
router.register(r'payments', PaymentViewSet)
router.register(r'payment-methods', PaymentMethodViewSet, basename='payment-methods')
router.register(r'pos-payments', POSPaymentViewSet, basename='pos-payments')

urlpatterns = [
    path('', include(router.urls)),
    path(
        'payments/stripe/connect/onboard/',
        StripeConnectOnboardingView.as_view({'post': 'create'}),
        name='stripe-connect-onboard',
    ),
    path(
        'payments/stripe/connect/login-link/<str:merchant_id>/',
        StripeConnectLoginLinkView.as_view({'get': 'retrieve'}),
        name='stripe-connect-login-link',
    ),
]
