import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from notifications.models import Notification
from notifications.services import NotificationDispatcher
from main.utils import get_business_managers_group_name

from .models import Review

logger = logging.getLogger(__name__)
dispatcher = NotificationDispatcher()


@receiver(post_save, sender=Review)
def handle_review_notifications(sender, instance, created, **kwargs):
    """Handle notifications when a review is received - send push notification to managers"""
    
    try:
        # Only send notification for newly created reviews
        if not created:
            return
        
        # Get appointment and related data
        appointment = instance.appointment
        if not appointment:
            logger.warning(f"Review {instance.id} has no appointment")
            return
        
        business = appointment.business
        if not business:
            logger.warning(f"Appointment {appointment.id} has no business")
            return
        
        business_id = business.id
        business_name = business.name or "Business"
        
        # Get client name
        client = appointment.client
        client_name = "A client"
        if client:
            client_name = client.get_full_name() or client.first_name or "A client"
        
        # Build notification message
        rating = instance.rating
        stars = "⭐" * rating
        title = f"New Review - {business_name}"
        
        body = f"{client_name} left a {rating}-star review"
        if instance.comment:
            # Truncate comment if too long
            comment = instance.comment[:100] + "..." if len(instance.comment) > 100 else instance.comment
            body += f": {comment}"
        body += f" {stars}"
        
        # Prepare notification data
        review_data = {
            "review_id": instance.id,
            "appointment_id": appointment.id,
            "rating": rating,
            "has_comment": bool(instance.comment),
        }
        print("review data", review_data)
        # Send push notification to business managers
        dispatcher.dispatchAsync(
            title=title,
            body=body,
            data=review_data,
            channel=Notification.Channel.PUSH,
            to=None,
            group_name=get_business_managers_group_name(business_id),
            business_id=business_id,
        )
        logger.info(f"Review notification sent to managers for review {instance.id}")
        
    except Exception as e:
        logger.error(f"Error handling review notifications: {e}", exc_info=True)
        return
