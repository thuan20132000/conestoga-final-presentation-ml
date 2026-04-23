from rest_framework import serializers
from .models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    actor_display = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = [
            'id', 'actor', 'actor_name', 'actor_display',
            'action', 'description',
            'target_content_type', 'target_object_id', 'target_repr',
            'changes', 'metadata', 'ip_address',
            'business', 'created_at',
        ]
        read_only_fields = fields

    def get_actor_display(self, obj):
        if obj.actor:
            return obj.actor.get_full_name() or str(obj.actor)
        return obj.actor_name or 'System'
