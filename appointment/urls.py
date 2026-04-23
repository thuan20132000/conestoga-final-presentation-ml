from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AppointmentViewSet,
    BusinessBookingViewSet,
    POSAppointmentViewSet,
    AppointmentServiceViewSet
)
from .views import SalesReportViewSet, TicketReportViewSet, SalaryReportViewSet
router = DefaultRouter()
router.register(r'appointments', AppointmentViewSet, basename='appointment')
router.register(r'business-booking', BusinessBookingViewSet, basename='business-booking')
router.register(r'appointment-services', AppointmentServiceViewSet, basename='appointment-service')
router.register(r'pos-appointments', POSAppointmentViewSet, basename='pos-appointments')
router.register(r'ticket-report', TicketReportViewSet, basename='ticket-report')
router.register(r'salary-report', SalaryReportViewSet, basename='salary-report')
urlpatterns = [
    path('', include(router.urls)),
]
