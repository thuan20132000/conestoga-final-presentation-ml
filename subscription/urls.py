from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import SubscriptionPlanViewSet, BusinessSubscriptionViewSet

router = DefaultRouter()
router.register('plans', SubscriptionPlanViewSet, basename='subscription-plan')

urlpatterns = [
    path('', include(router.urls)),
    path('my-subscription/', BusinessSubscriptionViewSet.as_view({'get': 'my_subscription'}), name='my-subscription'),
    path('subscribe/', BusinessSubscriptionViewSet.as_view({'post': 'subscribe'}), name='subscribe'),
    path('cancel/', BusinessSubscriptionViewSet.as_view({'post': 'cancel'}), name='cancel-subscription'),
    path('change-plan/', BusinessSubscriptionViewSet.as_view({'post': 'change_plan'}), name='change-plan'),
]
