from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"
        PUSH = "push", "Push"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="notifications", on_delete=models.CASCADE, null=True, blank=True
    )
    business = models.ForeignKey("business.Business", related_name="notifications", on_delete=models.CASCADE, null=True, blank=True)
    channel = models.CharField(max_length=16, choices=Channel.choices)
    to = models.CharField(max_length=255, help_text="Email address, phone number, or device token")
    title = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    data = models.JSONField(blank=True, null=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    

    def mark_sent(self):
        self.status = self.Status.SENT
        self.sent_at = timezone.now()
        self.error_message = ""
        self.save(update_fields=["status", "sent_at", "error_message"])

    def mark_failed(self, message: str):
        self.status = self.Status.FAILED
        self.error_message = message[:500]
        self.save(update_fields=["status", "error_message"])

    def __str__(self) -> str:
        return f"Notification(id={self.id}, channel={self.channel}, to={self.to}, status={self.status})"


class PushDevice(models.Model):
    PROVIDER_CHOICES = (
        ("fcm", "FCM"),
        ("apns", "APNS"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="push_devices", on_delete=models.CASCADE)
    business = models.ForeignKey("business.Business", related_name="push_devices", on_delete=models.CASCADE, null=True, blank=True)
    provider = models.CharField(max_length=16, choices=PROVIDER_CHOICES, default="fcm")
    token = models.CharField(max_length=512, unique=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"PushDevice(user={self.user_id}, provider={self.provider})"
