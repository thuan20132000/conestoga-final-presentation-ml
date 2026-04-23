from decimal import Decimal

from django.db import models
from django.utils import timezone
from pgvector.django import HnswIndex, VectorField
from simple_history.models import HistoricalRecords

from .enums import AIConfigurationStatus



class AIConfiguration(models.Model):
    """Stores AI behavior and integration settings for the OpenAI Agents SDK."""

    STATUS_CHOICES = [
        (AIConfigurationStatus.ACTIVE.value, "Active"),
        (AIConfigurationStatus.INACTIVE.value, "Inactive"),
        (AIConfigurationStatus.PENDING.value, "Pending"),
        (AIConfigurationStatus.ERROR.value, "Error"),
        (AIConfigurationStatus.DELETED.value, "Deleted"),
        (AIConfigurationStatus.ARCHIVED.value, "Archived"),
    ]

    LANGUAGE_CHOICES = [
        ("en-US", "English (US)"),
        ("en-GB", "English (GB)"),
        ("es-ES", "Spanish (ES)"),
        ("fr-FR", "French (FR)"),
        ("de-DE", "German (DE)"),
        ("it-IT", "Italian (IT)"),
        ("vi-VN", "Vietnamese (VN)"),
    ]

    MODEL_CHOICES = [
        ("gpt-realtime-mini", "GPT Realtime Mini"),
        ("gpt-realtime", "GPT Realtime"),
        ("gpt-realtime-1.5", "GPT Realtime 1.5"),
        ("gpt-4o-realtime-preview", "GPT 4o Realtime Preview"),
    ]

    VOICE_CHOICES = [
        ("alloy", "Alloy"),
        ("ash", "Ash"),
        ("ballad", "Ballad"),
        ("coral", "Coral"),
        ("echo", "Echo"),
        ("sage", "Sage"),
        ("shimmer", "Shimmer"),
        ("verse", "Verse"),
    ]

    business = models.ForeignKey(
        "business.Business", on_delete=models.CASCADE, related_name="ai_configs"
    )
    ai_name = models.CharField(max_length=100, default="Receptionist AI")
    greeting_message = models.TextField(default="Hello! How can I help you today?")
    prompt = models.TextField(
        default=(
            "You are a professional AI receptionist. Your role is to assist clients "
            "with appointments, provide business information, and answer questions "
            "about our services. Always be helpful, professional, and friendly. "
            "Route the caller to the appropriate specialist agent based on their needs."
        )
    )
    language = models.CharField(
        max_length=10, default="en-US", choices=LANGUAGE_CHOICES
    )
    voice = models.CharField(max_length=50, default="alloy", choices=VOICE_CHOICES)
    model_name = models.CharField(
        max_length=100, default="gpt-realtime-mini", choices=MODEL_CHOICES
    )
    temperature = models.FloatField(default=0.7)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=AIConfigurationStatus.ACTIVE.value,
    )
    
    forward_phone_number = models.CharField(max_length=50, blank=True, null=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "AI Configuration"
        verbose_name_plural = "AI Configurations"

    def __str__(self):
        return f"{self.ai_name} AI Config"


class CallSession(models.Model):
    """Tracks each phone call handled by the receptionist."""

    CALL_DIRECTION_CHOICES = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
    ]
    STATUS_CHOICES = [
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    OUTCOME_CHOICES = [
        ("successful", "Successful"),
        ("unsuccessful", "Unsuccessful"),
        ("unknown", "Unknown"),
    ]

    SENTIMENT_CHOICES = [
        ("positive", "Positive"),
        ("negative", "Negative"),
        ("neutral", "Neutral"),
    ]

    CATEGORY_CHOICES = [
        ("make_appointment", "Make Appointment"),
        ("cancel_appointment", "Cancel Appointment"),
        ("reschedule_appointment", "Reschedule Appointment"),
        ("ask_question", "Ask Question"),
        ("unknown", "Unknown"),
    ]

    business = models.ForeignKey(
        "business.Business",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calls",
    )
    direction = models.CharField(
        max_length=20, choices=CALL_DIRECTION_CHOICES, default="inbound"
    )
    caller_number = models.CharField(max_length=50)
    receiver_number = models.CharField(max_length=50, blank=True, null=True)
    call_sid = models.CharField(max_length=100, unique=True)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(blank=True, null=True)
    duration_seconds = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="in_progress"
    )
    transcript_summary = models.TextField(blank=True, null=True)
    conversation_transcript = models.JSONField(blank=True, null=True)
    outcome = models.CharField(
        max_length=20, choices=OUTCOME_CHOICES, default="unknown"
    )
    sentiment = models.CharField(
        max_length=20, choices=SENTIMENT_CHOICES, default="neutral"
    )
    category = models.CharField(
        max_length=30, choices=CATEGORY_CHOICES, default="unknown", blank=True
    )
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    history = HistoricalRecords()

    def __str__(self):
        return f"Call {self.call_sid} - {self.caller_number}"

    class Meta:
        verbose_name = "Call Session"
        verbose_name_plural = "Call Sessions"
        ordering = ["-started_at"]

    def calculate_cost(self):
        """Calculate the cost of the call."""
        total_seconds = (
            (self.ended_at - self.started_at).total_seconds()
            if self.ended_at and self.started_at
            else 0
        )
        minutes = Decimal(total_seconds) / 60 if total_seconds else 0
        cost = minutes * Decimal(self.business.cost_per_minute)
        self.cost = cost
        return cost

    def save(self, *args, **kwargs):
        """Save the call session."""
        self.calculate_cost()
        super().save(*args, **kwargs)


class ConversationMessage(models.Model):
    """Stores each message exchanged during the call."""

    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
    ]

    call = models.ForeignKey(
        CallSession, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    confidence_score = models.FloatField(blank=True, null=True)

    history = HistoricalRecords()

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class Intent(models.Model):
    """Represents detected intent from user speech (e.g., booking, cancel, inquiry)."""

    call = models.ForeignKey(
        CallSession, on_delete=models.CASCADE, related_name="intents"
    )
    name = models.CharField(max_length=100)
    confidence = models.FloatField(default=0.0)
    extracted_data = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    def __str__(self):
        return f"{self.name} ({self.confidence:.2f})"


class AudioRecording(models.Model):
    """Stores reference to call audio files."""

    call = models.ForeignKey(
        CallSession, on_delete=models.CASCADE, related_name="recordings"
    )
    audio_url = models.URLField()
    duration_seconds = models.IntegerField(blank=True, null=True)
    transcription_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    def __str__(self):
        return f"Recording for {self.call.call_sid}"


class SystemLog(models.Model):
    """Tracks system and AI events for debugging or analytics."""

    call = models.ForeignKey(
        CallSession,
        on_delete=models.CASCADE,
        related_name="logs",
        null=True,
        blank=True,
    )
    level = models.CharField(
        max_length=20,
        choices=[("info", "Info"), ("warning", "Warning"), ("error", "Error")],
    )
    message = models.TextField()
    metadata = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[" + self.level + "] " + self.message[:50]


class KnowledgeChunk(models.Model):
    """Per-business retrieval chunks used by the receptionist RAG layer."""

    SOURCE_TYPE_CHOICES = [
        ("business", "Business profile"),
        ("service", "Service"),
        ("service_category", "Service category"),
        ("staff", "Staff bio"),
        ("policy", "Policy"),
        ("hours", "Operating hours"),
        ("banner", "Banner"),
        ("ai_prompt", "AI configuration prompt"),
    ]

    EMBEDDING_DIMENSIONS = 1536

    business = models.ForeignKey(
        "business.Business",
        on_delete=models.CASCADE,
        related_name="knowledge_chunks",
    )
    source_type = models.CharField(max_length=32, choices=SOURCE_TYPE_CHOICES)
    source_id = models.CharField(max_length=64, blank=True, default="")
    title = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    embedding = VectorField(dimensions=EMBEDDING_DIMENSIONS)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "source_type"]),
            HnswIndex(
                name="kb_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]
        unique_together = [("business", "source_type", "source_id")]

    def __str__(self):
        return f"{self.business_id} [{self.source_type}] {self.title or self.source_id}"
