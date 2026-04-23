from django.db import models
import uuid
from main.models import SoftDeleteModel
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

class BusinessType(SoftDeleteModel):
    """Different types of businesses that can use the system."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, null=True)  # For UI icons
    
    class Meta:
        ordering = ['name']
        verbose_name = _('Business type')
        verbose_name_plural = _('Business types')
    
    def __str__(self):
        return self.name


class Business(SoftDeleteModel):
    """Represents a salon or company using the AI receptionist."""
    BUSINESS_STATUS_CHOICES = [
        ('active', _('Active')),
        ('inactive', _('Inactive')),
        ('suspended', _('Suspended')),
        ('pending', _('Pending Approval')),
    ]
    
    CURRENCY_CHOICES = [
        ('USD', 'USD'),
        ('CAD', 'CAD'),
        ('EUR', 'EUR'),
        ('GBP', 'GBP'),
        ('JPY', 'JPY'),
        ('AUD', 'AUD'),
        ('NZD', 'NZD'),
        ('VND', 'VND'),
        ('THB', 'THB'),
        ('MYR', 'MYR'),
        ('PHP', 'PHP'),
        ('IDR', 'IDR'),
        ('INR', 'INR'),
        ('PKR', 'PKR'),
        ('BDT', 'BDT'),
        ('KES', 'KES'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    business_type = models.ForeignKey(BusinessType, on_delete=models.PROTECT, related_name='businesses')
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    twilio_phone_number = models.CharField(max_length=50, blank=True, null=True)
    enable_ai_assistant = models.BooleanField(default=False)
    google_review_url = models.URLField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state_province = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, default="Canada")
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default="CAD")
    cost_per_minute = models.DecimalField(max_digits=10, decimal_places=2, default=0.5)
    description = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to='business_logos/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=BUSINESS_STATUS_CHOICES, default="active")
    
    class Meta:
        ordering = ['name']
        verbose_name = _('Business')
        verbose_name_plural = _('Businesses')
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
class OperatingHours(SoftDeleteModel):
    """Operating hours for each day of the week"""
    DAY_CHOICES = [
        (0, _('Monday')),
        (1, _('Tuesday')),
        (2, _('Wednesday')),
        (3, _('Thursday')),
        (4, _('Friday')),
        (5, _('Saturday')),
        (6, _('Sunday')),
    ]
    
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='operating_hours')
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    is_open = models.BooleanField(default=True)
    open_time = models.TimeField(blank=True, null=True)
    close_time = models.TimeField(blank=True, null=True)
    is_break_time = models.BooleanField(default=False, help_text=_("Has break time during the day"))
    break_start_time = models.TimeField(blank=True, null=True)
    break_end_time = models.TimeField(blank=True, null=True)
    
    class Meta:
        unique_together = ['business', 'day_of_week']
        ordering = ['day_of_week']
        verbose_name = _('Operating hours')
        verbose_name_plural = _('Operating hours')
    
    def __str__(self):
        day_name = dict(self.DAY_CHOICES)[self.day_of_week]
        if not self.is_open:
            return f"{day_name}: {str(_('Closed'))}"
        return f"{day_name}: {self.open_time} - {self.close_time}"


class BusinessSettings(SoftDeleteModel):
    TIMEZONE_CHOICES = [
        ('America/Toronto', 'America/Toronto'),
        ('America/New_York', 'America/New_York'),
        ('America/Los_Angeles', 'America/Los_Angeles'),
        ('America/Chicago', 'America/Chicago'),
        ('America/Phoenix', 'America/Phoenix'),
        ('America/Denver', 'America/Denver'),
        ('America/Kansas_City', 'America/Kansas_City'),
        ('America/Minneapolis', 'America/Minneapolis'),
        ('America/Houston', 'America/Houston'),
        ('America/Dallas', 'America/Dallas'),
        ('Asia/Saigon', 'Asia/Saigon'),
        ('Asia/Tokyo', 'Asia/Tokyo'),
        ('Asia/Seoul', 'Asia/Seoul'),
        ('Asia/Shanghai', 'Asia/Shanghai'),
        ('Asia/Hong_Kong', 'Asia/Hong_Kong'),
        ('Asia/Singapore', 'Asia/Singapore'),
        ('Asia/Bangkok', 'Asia/Bangkok'),
        ('Asia/Jakarta', 'Asia/Jakarta'),
        ('Asia/Manila', 'Asia/Manila'),
    ]
    LANGUAGE_CHOICES = [
        ("en", _("English")),
        ("vi", _("Vietnamese")),
    ]
        
    """Additional settings and preferences for the business"""
    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name='settings')
    
    # Timezone settings
    timezone = models.CharField(max_length=100, choices=TIMEZONE_CHOICES, default="America/Toronto")
    
    # Booking settings
    advance_booking_days = models.PositiveIntegerField(default=30, help_text=_("How many days in advance can clients book"))
    min_advance_booking_hours = models.PositiveIntegerField(default=2, help_text=_("Minimum hours in advance for booking"))
    max_advance_booking_days = models.PositiveIntegerField(default=90, help_text=_("Maximum days in advance for booking"))
    
    # Time slot settings
    time_slot_interval = models.PositiveIntegerField(default=15, help_text=_("Time slot interval in minutes"))
    buffer_time_minutes = models.PositiveIntegerField(default=0, help_text=_("Buffer time between appointments"))
    
    # Notification settings
    send_reminder_emails = models.BooleanField(default=True)
    send_reminder_sms = models.BooleanField(default=False)
    reminder_hours_before = models.PositiveIntegerField(default=24, help_text=_("Hours before appointment to send reminder"))
    send_confirmation_sms = models.BooleanField(default=False)
    send_confirmation_email = models.BooleanField(default=False)
    send_cancellation_sms = models.BooleanField(default=False)
    send_cancellation_email = models.BooleanField(default=False)
    
    # Payment settings
    currency = models.CharField(max_length=3, default="CAD")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.13, help_text=_("Tax rate as decimal (0.13 = 13%)"))
    require_payment_advance = models.BooleanField(default=False)
    
    # General settings
    preferred_language = models.CharField(
        max_length=5,
        choices=LANGUAGE_CHOICES,
        default="en",
        help_text=_("Preferred language used when request does not provide a supported Accept-Language header"),
    )
    allow_online_booking = models.BooleanField(default=True)
    require_client_phone = models.BooleanField(default=True)
    require_client_email = models.BooleanField(default=False)
    auto_confirm_appointments = models.BooleanField(default=False)
    
    # Gift card settings
    allow_online_gift_cards = models.BooleanField(default=False)
    
    gift_card_processing_fee_enabled = models.BooleanField(default=True)
    
    tax_with_cash_enabled = models.BooleanField(default=True)

    # Turn management settings
    half_turn_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=25.00,
        help_text=_("Service price threshold: above this = full turn, at or below = half turn"),
    )

    def __str__(self):
        return f"{str(_('Settings for'))} {self.business.name}"

    class Meta:
        verbose_name = _("Business settings")
        verbose_name_plural = _("Business settings")

class BusinessRoles(SoftDeleteModel):
    """Roles for the business"""
    ROLE_CHOICES = [
        ('Owner', _('Owner')),
        ('Manager', _('Manager')),
        ('Stylist', _('Stylist')),
        ('Technician', _('Technician')),
        ('Assistant', _('Assistant')),
        ('Receptionist', _('Receptionist')),
        ('Other', _('Other')),
    ]
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE, related_name='roles')
    name = models.CharField(max_length=100, choices=ROLE_CHOICES)
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = _('Business role')
        verbose_name_plural = _('Business roles')
    
    def __str__(self):
        return f"{self.business.name} - {self.name}"
    
    def is_managers(self):
        return self.name in ['Manager', 'Owner', 'Receptionist']
class BusinessOnlineBooking(SoftDeleteModel):
    """Online booking configuration for the business"""
    business = models.OneToOneField(
        Business, 
        on_delete=models.CASCADE, 
        related_name='online_booking',
        help_text=_("The business this online booking page belongs to")
    )
    name = models.CharField(max_length=255, help_text=_("Name of the online booking page"))
    slug = models.SlugField(
        max_length=255, 
        unique=True, 
        blank=True, 
        null=True,
        help_text=_("URL-friendly identifier for the booking page")
    )
    logo = models.ImageField(upload_to='business_logos/', blank=True, null=True)
    description = models.TextField(blank=True, null=True, help_text=_("Description shown on the booking page"))
    policy = models.TextField(blank=True, null=True, help_text=_("Booking policy/terms shown to clients"))
    
    # Booking settings
    interval_minutes = models.PositiveIntegerField(
        default=15, 
        help_text=_("Time slot interval in minutes")
    )
    buffer_time_minutes = models.PositiveIntegerField(
        default=0, 
        help_text=_("Buffer time between appointments in minutes")
    )
    
    # Status and visibility
    is_active = models.BooleanField(
        default=True, 
        help_text=_("Whether the online booking page is active and accessible")
    )
    
    # Shareable link
    shareable_link = models.URLField(
        blank=True, 
        null=True,
        help_text=_("Shareable URL for the online booking page")
    )
    
    class Meta:
        ordering = ['business__name', 'name']
        verbose_name = _('Online Booking')
        verbose_name_plural = _('Online Bookings')
    
    def __str__(self):
        return f"{self.business.name} - {self.name or str(_('Online Booking'))}"
    
    def save(self, *args, **kwargs):
        """Save the online booking configuration"""
        # Generate slug from name if not provided
        if not self.slug and self.name:
            from django.utils.text import slugify
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            # Check for existing slugs, excluding current instance if it exists
            queryset = BusinessOnlineBooking.objects.filter(slug=slug)
            if self.pk:
                queryset = queryset.exclude(pk=self.pk)
            while queryset.exists():
                slug = f"{base_slug}-{counter}"
                queryset = BusinessOnlineBooking.objects.filter(slug=slug)
                if self.pk:
                    queryset = queryset.exclude(pk=self.pk)
                counter += 1
            self.slug = slug
        
        super().save(*args, **kwargs)

class BusinessBanner(SoftDeleteModel):
    BANNER_TYPE_CHOICES = [
        ('promotion', _('Promotion')),
        ('info', _('Information')),
        ('alert', _('Alert')),
    ]
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE, related_name='banners')
    type = models.CharField(max_length=20, choices=BANNER_TYPE_CHOICES, default='info')
    title = models.CharField(max_length=120)
    message = models.TextField()
    cta_text = models.CharField(max_length=50, blank=True, null=True)
    cta_url = models.CharField(max_length=255, blank=True, null=True)
    start_at = models.DateTimeField(blank=True, null=True)
    end_at = models.DateTimeField(blank=True, null=True)

    dismissible = models.BooleanField(default=True)

    # Styling (optional but useful)
    background_color = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text=_("HEX or Tailwind class")
    )

    text_color = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )
    
    image = models.ImageField(upload_to='banners/', blank=True, null=True)
    
    is_active = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Business banner")
        verbose_name_plural = _("Business banners")
        indexes = [
            models.Index(fields=["business", "is_active"]),
        ]

    def __str__(self):
        return f"{self.business} | {self.title}"

    def is_visible(self):
        """
        Check if banner should be shown right now
        """
        now = timezone.now()

        if not self.is_active:
            return False

        if self.start_at and self.start_at > now:
            return False

        if self.end_at and self.end_at < now:
            return False

        return True


class BusinessFeedback(SoftDeleteModel):
    """Feedback from business owners to the platform."""
    CATEGORY_CHOICES = [
        ('bug', _('Bug')),
        ('feature_request', _('Feature Request')),
        ('general', _('General')),
        ('complaint', _('Complaint')),
    ]
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('reviewed', _('Reviewed')),
        ('in_progress', _('In Progress')),
        ('resolved', _('Resolved')),
        ('closed', _('Closed')),
    ]

    business = models.ForeignKey('Business', on_delete=models.CASCADE, related_name='feedbacks')
    submitted_by = models.ForeignKey('staff.Staff', on_delete=models.CASCADE, related_name='submitted_feedbacks')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    subject = models.CharField(max_length=255)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_response = models.TextField(null=True, blank=True)
    admin_responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Business Feedback')
        verbose_name_plural = _('Business Feedbacks')

    def __str__(self):
        return f"{self.business.name} - {self.subject}"