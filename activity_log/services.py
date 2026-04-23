import logging
from django.contrib.contenttypes.models import ContentType
from .models import ActivityLog

logger = logging.getLogger(__name__)


class ActivityLogService:

    @staticmethod
    def _get_client_ip(request):
        if not request:
            return None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    @classmethod
    def log(cls, *, business, action, description,
            actor=None, request=None,
            target=None, target_repr='',
            changes=None, metadata=None):
        """
        Log a business activity.

        Args:
            business: Business instance or UUID
            action: One of 'create', 'update', 'delete', 'status_change',
                    'payment', 'login', 'custom'
            description: Human-readable description
            actor: User instance. If None, extracted from request.
            request: HttpRequest for auto-extracting actor and IP.
            target: Optional model instance acted upon (uses ContentType).
            target_repr: Optional string representation of the target.
            changes: Optional dict of field changes.
            metadata: Optional dict of extra data.
        """
        try:
            if actor is None and request and hasattr(request, 'user') and request.user.is_authenticated:
                actor = request.user

            actor_name = ''
            if actor:
                actor_name = actor.get_full_name() if hasattr(actor, 'get_full_name') else str(actor)

            ip_address = cls._get_client_ip(request)

            target_content_type = None
            target_object_id = None
            if target is not None:
                target_content_type = ContentType.objects.get_for_model(target)
                target_object_id = str(target.pk)
                if not target_repr:
                    target_repr = str(target)[:255]

            ActivityLog.objects.create(
                business_id=business if not hasattr(business, 'pk') else business.pk,
                actor=actor,
                actor_name=actor_name[:255],
                action=action,
                description=description,
                target_content_type=target_content_type,
                target_object_id=target_object_id,
                target_repr=target_repr[:255] if target_repr else '',
                changes=changes,
                metadata=metadata,
                ip_address=ip_address,
            )
        except Exception as e:
            logger.error(f"Failed to create activity log: {e}", exc_info=True)
