from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReviewViewSet, BusinessReviewViewSet

router = DefaultRouter()
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'business-reviews', BusinessReviewViewSet, basename='business-review')

urlpatterns = [
    path('', include(router.urls)),
]

