from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from business.models import Business
from simple_history.models import HistoricalRecords
from main.models import SoftDeleteModel


class Client(SoftDeleteModel):
    LANGUAGE_CHOICES = [
        ("en", _("English")),
        ("vi", _("Vietnamese")),
    ]

    """Client information for appointments and services"""

    first_name = models.CharField(max_length=100, help_text="Client's first name")
    last_name = models.CharField(
        max_length=100, help_text="Client's last name", blank=True, null=True
    )
    email = models.EmailField(blank=True, null=True, help_text="Primary email address")
    phone = models.CharField(
        max_length=20, blank=True, null=True, help_text="Primary phone number"
    )
    date_of_birth = models.DateField(
        blank=True, null=True, help_text="Date of birth for age verification"
    )

    # Address information
    address_line1 = models.CharField(
        max_length=255, blank=True, null=True, help_text="Street address"
    )
    address_line2 = models.CharField(
        max_length=255, blank=True, null=True, help_text="Apartment, suite, etc."
    )
    city = models.CharField(max_length=100, blank=True, null=True, help_text="City")
    state_province = models.CharField(
        max_length=100, blank=True, null=True, help_text="State or Province"
    )
    postal_code = models.CharField(
        max_length=20, blank=True, null=True, help_text="Postal/ZIP code"
    )
    country = models.CharField(
        max_length=100, blank=True, null=True, help_text="Country"
    )

    # Emergency contact
    emergency_contact_name = models.CharField(
        max_length=200, blank=True, null=True, help_text="Emergency contact full name"
    )
    emergency_contact_phone = models.CharField(
        max_length=20, blank=True, null=True, help_text="Emergency contact phone"
    )
    emergency_contact_relation = models.CharField(
        max_length=100, blank=True, null=True, help_text="Relationship to client"
    )

    # Client preferences and information
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=[
            ("email", "Email"),
            ("phone", "Phone"),
            ("sms", "SMS"),
            ("none", "No Contact"),
        ],
        default="email",
        help_text="Preferred method of contact",
    )
    preferred_language = models.CharField(
        max_length=5,
        choices=LANGUAGE_CHOICES,
        default="en",
        help_text=_("Preferred language for client-facing messages"),
    )
    notes = models.TextField(
        blank=True, null=True, help_text="Special notes about the client"
    )
    medical_notes = models.TextField(
        blank=True, null=True, help_text="Medical conditions or allergies"
    )

    # Business relationship
    primary_business = models.ForeignKey(
        Business,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_clients",
        help_text="Primary business this client is associated with",
    )

    # Status and metadata
    is_active = models.BooleanField(
        default=True, help_text="Whether the client is active"
    )
    is_vip = models.BooleanField(default=False, help_text="VIP client status")
    bonus_time_minutes = models.PositiveIntegerField(
        default=0,
        help_text="Extra minutes automatically added to each service duration for this client",
    )
    minimum_booking_duration_minutes = models.PositiveIntegerField(
        default=0, help_text="Minimum booking duration in minutes for this client"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name = "Client"
        verbose_name_plural = "Clients"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def get_full_name(self):
        """Return the client's full name"""
        return f"{self.first_name} {self.last_name if self.last_name else ''}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class ClientSocialAccount(models.Model):
    """Links a Client to a third-party OAuth provider identity."""

    PROVIDER_CHOICES = [
        ("google", "Google"),
        ("facebook", "Facebook"),
    ]

    client = models.ForeignKey(
        Client,
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
        verbose_name = "Client Social Account"
        verbose_name_plural = "Client Social Accounts"

    def __str__(self):
        return f"{self.client} via {self.get_provider_display()} ({self.provider_user_id})"


class ClientOTP(models.Model):
    """Stores OTP codes for client passwordless authentication"""

    IDENTIFIER_TYPE_CHOICES = [
        ("email", "Email"),
        ("phone", "Phone"),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="otps")
    code = models.CharField(max_length=6)
    identifier = models.CharField(max_length=255)
    identifier_type = models.CharField(max_length=10, choices=IDENTIFIER_TYPE_CHOICES)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="client_otps"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Client OTP"
        verbose_name_plural = "Client OTPs"

    def __str__(self):
        return f"OTP for {self.client} ({self.identifier_type}: {self.identifier})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


class ClientPushSubscription(models.Model):
    """Bridges Client to django-webpush via group-based subscriptions"""

    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="push_subscriptions"
    )
    subscription = models.ForeignKey(
        "webpush.SubscriptionInfo", on_delete=models.CASCADE
    )
    push_info = models.ForeignKey("webpush.PushInformation", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Client Push Subscription"
        verbose_name_plural = "Client Push Subscriptions"

    def __str__(self):
        return f"Push subscription for {self.client}"
