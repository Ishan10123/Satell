import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations")
    title = models.CharField(max_length=200, default="New conversation")
    title_is_manual = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    share_token_hash = models.CharField(max_length=64, blank=True, db_index=True)
    share_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "-created_at")
        indexes = [models.Index(fields=("user", "-updated_at"), name="conv_user_updated_idx")]

    def __str__(self) -> str:
        return self.title


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.COMPLETE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        indexes = [models.Index(fields=("conversation", "created_at"), name="msg_conv_created_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(role__in=("user", "assistant")), name="msg_role_valid"),
            models.CheckConstraint(condition=Q(status__in=("pending", "complete", "failed")), name="msg_status_valid"),
        ]

    def __str__(self) -> str:
        return f"{self.role} message {self.pk}"


class CitationSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="citations")
    citation_id = models.CharField(max_length=32)
    source_id = models.CharField(max_length=128)
    document_id = models.CharField(max_length=128)
    chunk_id = models.CharField(max_length=128, blank=True)
    title = models.CharField(max_length=500)
    page_references = models.JSONField(default=list, blank=True)
    section = models.CharField(max_length=1000, blank=True)
    source_reference = models.URLField(max_length=2048, blank=True)

    class Meta:
        ordering = ("citation_id",)
        constraints = [models.UniqueConstraint(fields=("message", "citation_id"), name="citation_msg_id_unique")]
        indexes = [models.Index(fields=("document_id",), name="citation_document_idx")]

    def __str__(self) -> str:
        return f"{self.citation_id} for {self.message_id}"


class GenerationMetadata(models.Model):
    class VerificationStatus(models.TextChoices):
        SYNTHETIC = "synthetic", "Synthetic mock response"
        TRUSTED_METADATA = "trusted_metadata", "Trusted application metadata"
        VERIFIED = "verified", "Claims verified"
        PARTIALLY_VERIFIED = "partially_verified", "Some claims omitted by verifier"
        ABSTAINED = "abstained", "Insufficient authorized evidence"
        NOT_REPORTED = "not_reported", "Not reported by RAG API"
        FAILED = "failed", "Generation failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="generation_metadata")
    request_id = models.CharField(max_length=128, db_index=True)
    retrieval_mode = models.CharField(max_length=32, blank=True)
    model_version = models.CharField(max_length=128, null=True, blank=True)
    index_version = models.CharField(max_length=128, null=True, blank=True)
    stage_timings = models.JSONField(default=dict, blank=True)
    diagnostics = models.JSONField(default=dict, blank=True)
    verification_status = models.CharField(max_length=24, choices=VerificationStatus.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("message",), name="gen_metadata_message_unique")]

    def __str__(self) -> str:
        return f"Generation metadata for {self.message_id}"
