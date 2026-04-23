from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from simple_history.models import HistoricalRecords

from payment.models import PaymentStatusType
from main.models import SoftDeleteModel

from payment.models import PaymentMethodType

class AppointmentStatusType(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    IN_SERVICE = "in_service", "In Service"
    CHECKED_IN = "checked_in", "Checked In"
    CHECKED_OUT = "checked_out", "Checked Out"
    CANCELLED = "cancelled", "Cancelled"
    NO_SHOW = "no_show", "No Show"
    PENDING_PAYMENT = "pending_payment", "Pending Payment"
    

class BookingSourceType(models.TextChoices):
    ONLINE = "online", "Online Booking"
    PHONE = "phone", "Phone Booking"
    WALK_IN = "walk_in", "Walk-in"
    STAFF = "staff", "Staff Booking"
    AI_RECEPTIONIST = "ai_receptionist", "AI Receptionist"
    

class Appointment(SoftDeleteModel):
    """Main appointment model"""
    
    # Related entities
    business = models.ForeignKey(
        'business.Business', 
        on_delete=models.SET_NULL, 
        related_name='appointments',
        null=True,
        blank=True
    )
    
    client = models.ForeignKey(
        'client.Client', 
        on_delete=models.SET_NULL, 
        related_name='appointments', 
        null=True, 
        blank=True
    )

    # Appointment timing
    appointment_date = models.DateField()

    # Status and tracking
    status = models.CharField(
        max_length=50, 
        choices=AppointmentStatusType.choices, 
        default=AppointmentStatusType.SCHEDULED,
        help_text="Status of the appointment"
    )
    
    payment_status = models.CharField(
        max_length=50, 
        choices=PaymentStatusType.choices, 
        default=PaymentStatusType.NOT_PAID,
        help_text="Status of the payment for the appointment"
    )
    notes = models.TextField(blank=True, null=True, help_text="Appointment notes")
    internal_notes = models.TextField(blank=True, null=True, help_text="Internal notes (not visible to client)")

    # Booking tracking
    booked_by = models.ForeignKey(
        'staff.Staff', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='booked_appointments'
    )
    booking_source = models.CharField(
        max_length=50, 
        choices=BookingSourceType.choices, 
        default=BookingSourceType.ONLINE,
        help_text="Source of the booking"
    )
    
    # send review request to client
    send_review_request = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    metadata = models.JSONField(null=True, blank=True)
    
    history = HistoricalRecords()

    class Meta:
        ordering = ['appointment_date']

    def __str__(self):
        return f"{self.id} - {self.appointment_date}"

    @property
    def is_past(self):
        """Check if appointment is in the past"""
        return self.appointment_date < timezone.now().date()

    @property
    def is_today(self):
        """Check if appointment is today"""
        return self.appointment_date == timezone.now().date()

    @property
    def is_upcoming(self):
        """Check if appointment is in the future"""
        return not self.is_past

    def get_status_display_color(self):
        """Get the color for status display"""
        return self.status

    

class AppointmentService(SoftDeleteModel):
    """Appointment service model"""
    SERVICE_REQUEST_STATUS_CHOICES = [
        ('requested', 'Requested'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ]
    appointment = models.ForeignKey(
        Appointment, 
        on_delete=models.SET_NULL, 
        related_name='appointment_services',
        null=True,
        blank=True
    )
    service = models.ForeignKey(
        'service.Service', 
        on_delete=models.SET_NULL, 
        related_name='appointment_services',
        null=True,
        blank=True
    )
    
    staff = models.ForeignKey(
        'staff.Staff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointment_services'
    )
    
    is_staff_request = models.BooleanField(default=False)
    
    custom_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
    )
    
    discount_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
    )
    
    discount_percentage = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
    )
    
    custom_duration = models.IntegerField(
        help_text="Duration in minutes", 
        null=True, 
        blank=True,
    )
    
    start_at = models.DateTimeField(null=True, blank=True, help_text="Start time for the service")
    end_at = models.DateTimeField(null=True, blank=True, help_text="End time for the service")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    tip_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
    )
    
    tip_method = models.CharField(
        max_length=50,
        choices=PaymentMethodType.choices,
        default=None,
        null=True,
        blank=True,
        help_text="Method of tip payment"
    )
    
    metadata = models.JSONField(null=True, blank=True)
    
    history = HistoricalRecords()
    
    class Meta:
        ordering = ['start_at']

    def __str__(self):
        return f"{self.appointment} - {self.service} - {self.start_at} - {self.end_at}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

