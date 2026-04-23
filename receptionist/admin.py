from django.contrib import admin
import json
from django_json_widget.widgets import JSONEditorWidget
from django.db import models

from .models import (
    AIConfiguration,
    CallSession,
    ConversationMessage,
    Intent,
    AudioRecording,
    SystemLog,
    KnowledgeChunk,
)


@admin.register(AIConfiguration)
class AIConfigurationAdmin(admin.ModelAdmin):
    list_display = ("business", "ai_name", "language", "voice", "model_name", "updated_at")
    search_fields = ("business__name", "ai_name", "model_name")
    list_filter = ("language", "voice")


@admin.register(CallSession)
class CallSessionAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget},
    }
    
    list_display = ("call_sid", "business", "direction", "caller_number", "receiver_number", "status", "started_at_with_seconds", "ended_at_with_seconds", "duration_in_seconds")
    search_fields = ("call_sid", "caller_number", "receiver_number", "business__name")
    list_filter = ("direction", "status", "business")
    date_hierarchy = "started_at"
    
    # readonly_fields = ("conversation_transcript",)
    def started_at_with_seconds(self, obj):
        if obj.started_at:
            return obj.started_at.strftime("%Y-%m-%d %H:%M:%S")
        return "-"
    
    def ended_at_with_seconds(self, obj):
        if obj.ended_at:
            return obj.ended_at.strftime("%Y-%m-%d %H:%M:%S")
        return "-"

    def duration_in_seconds(self, obj):
        if obj.started_at and obj.ended_at:
                return int((obj.ended_at - obj.started_at).total_seconds())
        return "-"
    
    ended_at_with_seconds.short_description = "Ended At"
    ended_at_with_seconds.admin_order_field = "ended_at"

    started_at_with_seconds.short_description = "Started At"
    started_at_with_seconds.admin_order_field = "started_at"
    
    duration_in_seconds.short_description = "Duration in Seconds"
    duration_in_seconds.admin_order_field = "duration_seconds"


@admin.register(ConversationMessage)
class ConversationMessageAdmin(admin.ModelAdmin):
    list_display = ("call", "role", "short_content", "timestamp", "confidence_score")
    search_fields = ("call__call_sid", "content")
    list_filter = ("role",)

    def short_content(self, obj):
        return (obj.content[:75] + "...") if len(obj.content) > 75 else obj.content
    short_content.short_description = "Content"


@admin.register(Intent)
class IntentAdmin(admin.ModelAdmin):
    list_display = ("call", "name", "confidence", "created_at")
    search_fields = ("call__call_sid", "name")
    list_filter = ("name",)


@admin.register(AudioRecording)
class AudioRecordingAdmin(admin.ModelAdmin):
    list_display = ("call", "audio_url", "duration_seconds", "created_at")
    search_fields = ("call__call_sid", "audio_url")


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ("call", "level", "short_message", "created_at")
    search_fields = ("call__call_sid", "message")
    list_filter = ("level",)

    def short_message(self, obj):
        return (obj.message[:75] + "...") if len(obj.message) > 75 else obj.message
    short_message.short_description = "Message"


@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(admin.ModelAdmin):
    list_display = ("business", "source_type", "source_id", "title", "updated_at")
    search_fields = ("business__name", "source_type", "source_id", "title", "content")
    list_filter = ("source_type", "business")
