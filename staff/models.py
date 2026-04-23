from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
import uuid
from main.models import SoftDeleteModel
import secrets


class Staff(AbstractUser, SoftDeleteModel):
    """Staff members working at the business"""
    
    
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE, null=True, blank=True, related_name='staff')
    phone = models.CharField(max_length=50, blank=True, null=True)
    role = models.ForeignKey(
        'business.BusinessRoles', 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL, 
        related_name='staff',
        help_text="The role of the staff member in the business"
    )
    is_active = models.BooleanField(default=True)
    is_online_booking_allowed = models.BooleanField(default=True)
    is_payment_processing_allowed = models.BooleanField(default=True)
    hire_date = models.DateTimeField(null=True, blank=True, default=timezone.now)
    bio = models.TextField(blank=True, null=True)
    photo = models.ImageField(upload_to='staff_photos/', blank=True, null=True)
    staff_code = models.IntegerField(blank=True, null=True, unique=True)
    commission_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.business})"
    
    def create_default_working_hours(self):
        from datetime import time
        for day in range(7):
            StaffWorkingHours.objects.create(staff=self, day_of_week=day, start_time=time(9, 30), end_time=time(17, 30))
        return self
    
    def save(self, *args, **kwargs):
        if not self.username:
            self.username = str(uuid.uuid4())
            
        if not self.staff_code:
            self.staff_code = secrets.choice(range(10000, 99999))
            while Staff.objects.filter(staff_code=self.staff_code).exists():
                self.staff_code = secrets.choice(range(10000, 99999))
            
        super().save(*args, **kwargs)
        
        if not self.working_hours.all():
            self.create_default_working_hours()

class StaffSocialAccount(models.Model):
    """Links a Staff/owner to a third-party OAuth provider identity."""

    PROVIDER_CHOICES = [
        ("google", "Google"),
        ("facebook", "Facebook"),
    ]

    staff = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        related_name="social_accounts",
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_user_id = models.CharField(
        max_length=255,
        help_text="Unique user ID returned by the provider (Google sub / Facebook id)",
    )
    email = models.EmailField(
        blank=True,
        null=True,
        help_text="Email address as returned by the provider at time of login",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("provider", "provider_user_id")]
        verbose_name = "Staff Social Account"
        verbose_name_plural = "Staff Social Accounts"

    def __str__(self):
        return f"{self.staff} via {self.get_provider_display()} ({self.provider_user_id})"


class StaffService(SoftDeleteModel):
    """Many-to-many relationship between staff and services they can provide"""
    staff = models.ForeignKey('staff.Staff', on_delete=models.CASCADE, related_name='staff_services')
    service = models.ForeignKey('service.Service', on_delete=models.CASCADE, related_name='staff_services')
    custom_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    custom_duration = models.IntegerField(help_text="Duration in minutes", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_online_booking = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False, help_text="Primary service for this staff member")
    
    class Meta:
        unique_together = ['staff', 'service']
    
    def __str__(self):
        return f"{self.staff.get_full_name()} - Service {self.service.name}"
    
class StaffWorkingHours(SoftDeleteModel):
    """Staff working hours"""
    DAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    staff = models.ForeignKey('staff.Staff', on_delete=models.CASCADE, related_name='working_hours')
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    is_working = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['staff', 'day_of_week']
    
    def __str__(self):
        return f"{self.staff} - {self.day_of_week}"
    
class StaffWorkingHoursOverride(SoftDeleteModel):
    staff = models.ForeignKey('staff.Staff', on_delete=models.CASCADE, related_name='working_hours_overrides')
    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    is_working = models.BooleanField(default=True)
    reason = models.CharField(max_length=255, null=True, blank=True)
    
    class Meta:
        unique_together = ['staff', 'date']
        
    def __str__(self):
        return f"{self.staff} - {self.date} - {self.start_time} to {self.end_time} - {self.reason}"

class StaffOffDay(SoftDeleteModel):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='staff_off_days')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.staff} - {self.start_date} to {self.end_date} - {self.reason}"


class TimeEntry(SoftDeleteModel):
    STATUS_CHOICES = (
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('ADJUSTED', 'Adjusted'),
        ('AUTO_CLOSED', 'Auto Closed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    clock_in = models.DateTimeField()
    clock_out = models.DateTimeField(null=True, blank=True)

    break_minutes = models.PositiveIntegerField(default=0)
    total_minutes = models.PositiveIntegerField(null=True, blank=True)
    overtime_minutes = models.PositiveIntegerField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['staff', 'clock_out']),
        ]

    def calculate_totals(self):
        """No floats. Minutes only."""
        worked = int((self.clock_out - self.clock_in).total_seconds() // 60)
        worked -= self.break_minutes
        self.total_minutes = max(worked, 0)

        regular = 8 * 60
        self.overtime_minutes = max(self.total_minutes - regular, 0)
        
    def save(self, *args, **kwargs):
        if self.clock_out:
            self.calculate_totals()
            self.status = 'COMPLETED'
        else:
            self.status = 'IN_PROGRESS'
            self.total_minutes = 0
            self.overtime_minutes = 0
        super().save(*args, **kwargs)