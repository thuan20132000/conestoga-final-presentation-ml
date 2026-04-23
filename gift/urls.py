from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import GiftCardViewSet, GiftCardTransactionViewSet, GiftCardCheckoutViewSet

# Create router and register viewsets
router = DefaultRouter()
router.register(r'gift-cards', GiftCardViewSet, basename='gift-cards')
router.register(r'gift-card-transactions', GiftCardTransactionViewSet, basename='gift-card-transactions')
urlpatterns = [
    path('', include(router.urls)),
    path('gift-card-checkouts/', GiftCardCheckoutViewSet.as_view(), name='gift-card-checkouts'),
]
