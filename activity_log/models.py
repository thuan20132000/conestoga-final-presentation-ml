from django.db import models
from django.conf import settings


class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('status_change', 'Status Change'),
        ('payment', 'Payment'),
        ('login', 'Login'),
        ('custom', 'Custom'),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs',
    )
    actor_name = models.CharField(max_length=255, blank=True)
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    description = models.TextField()
    target_content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    target_object_id = models.CharField(max_length=255, null=True, blank=True)
    target_repr = models.CharField(max_length=255, blank=True)
    changes = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    business = models.ForeignKey(
        'business.Business',
        on_delete=models.CASCADE,
        related_name='activity_logs',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', '-created_at']),
            models.Index(fields=['action']),
            models.Index(fields=['target_content_type', 'target_object_id']),
        ]

    def __str__(self):
        return f"{self.actor_name} {self.action} - {self.description[:50]}"
