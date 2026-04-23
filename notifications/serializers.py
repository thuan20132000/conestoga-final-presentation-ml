from rest_framework import serializers

from .models import Notification, PushDevice
from webpush.models import PushInformation, Group, SubscriptionInfo

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "user",
            "channel",
            "to",
            "title",
            "body",
            "data",
            "status",
            "error_message",
            "created_at",
            "sent_at",
        ]
        read_only_fields = ("status", "error_message", "created_at", "sent_at")


class PushDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushDevice
        fields = ["id", "user", "provider", "token", "active", "created_at"]
        read_only_fields = ("created_at",)


# WebPush Serializers

class PushGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name", "created_at", "updated_at"]
        read_only_fields = ("created_at", "updated_at")
        
class PushSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionInfo
        fields = ["id", "endpoint", "auth", "p256dh", "created_at", "updated_at"]
        read_only_fields = ("created_at", "updated_at")
        
class PushInformationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushInformation
        fields = ["id", "subscription", "user", "group"]
        
