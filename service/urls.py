from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ServiceCategoryViewSet, ServiceViewSet

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'categories', ServiceCategoryViewSet, basename='service-category')
router.register(r'services', ServiceViewSet, basename='service')

# The API URLs are now determined automatically by the router
urlpatterns = [
    path('', include(router.urls)),
]
