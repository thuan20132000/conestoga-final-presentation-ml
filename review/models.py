from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from simple_history.models import HistoricalRecords
from main.models import SoftDeleteModel


class Review(SoftDeleteModel):
    """Review model for client appointments"""
    
    # Related entities
    appointment = models.ForeignKey(
        'appointment.Appointment',
        on_delete=models.CASCADE,
        related_name='reviews',
        help_text="The appointment being reviewed"
    )
    
    # Review content
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars"
    )
    
    comment = models.TextField(
        blank=True,
        null=True,
        help_text="Optional review comment"
    )
    
    # Review metadata
    is_visible = models.BooleanField(
        default=True,
        help_text="Whether the review is visible to others"
    )
    
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether the review is verified (e.g., confirmed appointment completion)"
    )
    
    # Timestamps
    reviewed_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the review was submitted"
    )
    
    is_active = models.BooleanField(default=True)
    
    metadata = models.JSONField(null=True, blank=True)
    
    history = HistoricalRecords()
    
    class Meta:
        ordering = ['-reviewed_at', '-created_at']
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        indexes = [
            models.Index(fields=['appointment']),
            models.Index(fields=['rating']),
            models.Index(fields=['is_visible', 'is_active']),
        ]
    
    def __str__(self):
        return f"Review {self.id} - {self.rating} stars - {self.appointment}"
    
    def save(self, *args, **kwargs):
        # Auto-verify if appointment is completed
        if self.appointment and self.appointment.completed_at:
            self.is_verified = True
        super().save(*args, **kwargs)
    
    @property
    def is_recent(self):
        """Check if review was submitted within last 7 days"""
        return (timezone.now() - self.reviewed_at).days <= 7
