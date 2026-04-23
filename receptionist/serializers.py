from rest_framework import serializers

from business.serializers import (BusinessDetailSerializer,
                                  BusinessListSerializer)

from .models import (AIConfiguration, AudioRecording, CallSession,
                     ConversationMessage, Intent, SystemLog)


class AIConfigurationSerializer(serializers.ModelSerializer):
    """Serializer for AIConfiguration model."""

    business_name = serializers.CharField(source="business.name", read_only=True)

    class Meta:
        model = AIConfiguration
        fields = [
            "id",
            "business",
            "business_name",
            "ai_name",
            "greeting_message",
            "language",
            "voice",
            "model_name",
            "temperature",
            "forward_phone_number",
            "created_at",
            "updated_at",
            "status",
            "prompt",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CallSessionSerializer(serializers.ModelSerializer):
    """Serializer for CallSession model."""

    business_name = serializers.CharField(source="business.name", read_only=True)
    duration_formatted = serializers.SerializerMethodField()
    duration_in_seconds = serializers.SerializerMethodField()
    outcome = serializers.CharField(read_only=True)
    sentiment = serializers.CharField(read_only=True)

    class Meta:
        model = CallSession
        fields = [
            "id",
            "business",
            "business_name",
            "direction",
            "caller_number",
            "receiver_number",
            "call_sid",
            "started_at",
            "ended_at",
            "duration_seconds",
            "duration_formatted",
            "duration_in_seconds",
            "status",
            "transcript_summary",
            "conversation_transcript",
            "outcome",
            "sentiment",
            "category",
            "cost",
        ]
        read_only_fields = ["id", "duration_formatted"]

    def get_duration_formatted(self, obj):
        """Format duration in MM:SS format."""
        duration = obj.duration_seconds
        return "00:00"

    def get_duration_in_seconds(self, obj):
        """Get duration in seconds."""
        if obj.ended_at and obj.started_at:
            duration = obj.ended_at - obj.started_at
            if duration:
                return duration.total_seconds()
            return 0
        return 0


class ConversationMessageSerializer(serializers.ModelSerializer):
    """Serializer for ConversationMessage model."""

    call_sid = serializers.CharField(source="call.call_sid", read_only=True)

    class Meta:
        model = ConversationMessage
        fields = [
            "id",
            "call",
            "call_sid",
            "role",
            "content",
            "timestamp",
            "confidence_score",
        ]
        read_only_fields = ["id", "timestamp"]


class IntentSerializer(serializers.ModelSerializer):
    """Serializer for Intent model."""

    call_sid = serializers.CharField(source="call.call_sid", read_only=True)

    class Meta:
        model = Intent
        fields = [
            "id",
            "call",
            "call_sid",
            "name",
            "confidence",
            "extracted_data",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class AudioRecordingSerializer(serializers.ModelSerializer):
    """Serializer for AudioRecording model."""

    call_sid = serializers.CharField(source="call.call_sid", read_only=True)

    class Meta:
        model = AudioRecording
        fields = [
            "id",
            "call",
            "call_sid",
            "audio_url",
            "duration_seconds",
            "transcription_text",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class SystemLogSerializer(serializers.ModelSerializer):
    """Serializer for SystemLog model."""

    call_sid = serializers.CharField(source="call.call_sid", read_only=True)

    class Meta:
        model = SystemLog
        fields = [
            "id",
            "call",
            "call_sid",
            "level",
            "message",
            "metadata",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


# Detailed serializers for nested relationships
class CallSessionDetailSerializer(CallSessionSerializer):
    """Detailed serializer for CallSession with related data."""

    messages = ConversationMessageSerializer(many=True, read_only=True)
    intents = IntentSerializer(many=True, read_only=True)
    recordings = AudioRecordingSerializer(many=True, read_only=True)
    logs = SystemLogSerializer(many=True, read_only=True)

    class Meta(CallSessionSerializer.Meta):
        fields = CallSessionSerializer.Meta.fields + [
            "messages",
            "intents",
            "recordings",
            "logs",
        ]


class BusinessDetailSerializer(BusinessDetailSerializer):
    """Detailed serializer for Business with AI config and calls."""

    ai_config = AIConfigurationSerializer(read_only=True)
    calls = CallSessionSerializer(many=True, read_only=True)
    calls_count = serializers.SerializerMethodField()
    recent_calls = serializers.SerializerMethodField()

    class Meta(BusinessDetailSerializer.Meta):
        fields = BusinessDetailSerializer.Meta.fields + [
            "ai_config",
            "calls",
            "calls_count",
            "recent_calls",
        ]

    def get_calls_count(self, obj):
        """Get total number of calls for this business."""
        return obj.calls.count()

    def get_recent_calls(self, obj):
        """Get the 5 most recent calls."""
        recent = obj.calls.order_by("-started_at")[:5]
        return CallSessionSerializer(recent, many=True).data


# Statistics and analytics serializers
class CallStatisticsSerializer(serializers.Serializer):
    """Serializer for call statistics."""

    total_calls = serializers.IntegerField()
    completed_calls = serializers.IntegerField()
    failed_calls = serializers.IntegerField()
    in_progress_calls = serializers.IntegerField()
    average_duration = serializers.FloatField()
    total_duration = serializers.IntegerField()
    calls_by_status = serializers.DictField()
    calls_by_day = serializers.DictField()


class BusinessStatisticsSerializer(serializers.Serializer):
    """Serializer for business statistics."""

    business = BusinessDetailSerializer()
    total_calls = serializers.IntegerField()
    completed_calls = serializers.IntegerField()
    failed_calls = serializers.IntegerField()
    average_duration = serializers.FloatField()
    total_duration = serializers.IntegerField()
    recent_activity = serializers.ListField()


class IntentStatisticsSerializer(serializers.Serializer):
    """Serializer for intent statistics."""

    intent_name = serializers.CharField()
    count = serializers.IntegerField()
    average_confidence = serializers.FloatField()
    success_rate = serializers.FloatField()


# API response serializers
class APIResponseSerializer(serializers.Serializer):
    """Standard API response serializer."""

    success = serializers.BooleanField()
    message = serializers.CharField()
    data = serializers.JSONField(required=False)
    errors = serializers.JSONField(required=False)
