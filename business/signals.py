import logging
from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import BusinessFeedback
from notifications.services import EmailService, NotificationDispatcher

logger = logging.getLogger(__name__)
dispatcher = NotificationDispatcher()


@receiver(pre_save, sender=BusinessFeedback)
def handle_feedback_resolved(sender, instance, **kwargs):
    """Send email and push notification when feedback is resolved."""
    if not instance.pk:
        return

    try:
        old = BusinessFeedback.objects.get(pk=instance.pk)
    except BusinessFeedback.DoesNotExist:
        return

    if old.status == instance.status or instance.status != 'resolved':
        return

    user = instance.submitted_by
    business = instance.business

    # Send email notification
    if user.email:
        EmailService().send_async(
            subject=f"Your feedback has been resolved – {instance.subject}",
            to_email=user.email,
            template='emails/feedback_resolved.html',
            context={
                'submitted_by_name': user.get_full_name() or user.username,
                'business_name': business.name,
                'category': instance.get_category_display(),
                'subject': instance.subject,
                'message': instance.message,
                'admin_response': instance.admin_response or '',
            },
        )

    # Send push notification
    from main.utils import get_business_managers_group_name
    group_name = get_business_managers_group_name(business.id)
    dispatcher.dispatchAsync(
        channel='push',
        to=user,
        title='Feedback Resolved',
        body=f'Your feedback "{instance.subject}" has been resolved.',
        business_id=str(business.id),
        group_name=group_name,
    )
