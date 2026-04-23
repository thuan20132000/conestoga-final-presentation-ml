from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StaffTurnViewSet, TurnServiceViewSet

router = DefaultRouter()
router.register(r'staff-turns', StaffTurnViewSet, basename='staff-turns')
router.register(r'turn-services', TurnServiceViewSet, basename='turn-services')

urlpatterns = [
    path('', include(router.urls)),
]
