import uuid
import time

from django.conf import settings
from django.contrib import messages as flash_messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from conversations.models import CitationSnapshot, Conversation, GenerationMetadata, Message
from conversations.title_utils import title_from_first_question
from accounts.founder_metadata import answer_creator_question
from accounts.models import UserPreferences
from rag_client import RAGClientError, RAGClientInputTooLarge, get_rag_client

from .forms import MAX_MESSAGE_CHARS, MessageForm


@login_required
@require_POST
def message_create(request: HttpRequest, conversation_id: uuid.UUID) -> HttpResponse:
    # Scope the lookup in SQL so a guessed UUID for another user is indistinguishable
    # from a missing conversation.
    conversation = get_object_or_404(Conversation.objects.filter(user=request.user), pk=conversation_id)
    if conversation.locked_at:
        flash_messages.error(request, "This conversation is locked. Unlock it before sending another message.")
        return redirect("conversations:detail", conversation_id=conversation.pk)
    form = MessageForm(request.POST)
    if not form.is_valid():
        flash_messages.error(request, f"Enter a message of 1 to {MAX_MESSAGE_CHARS} characters.")
        return redirect("conversations:detail", conversation_id=conversation.pk)
    content = form.cleaned_data["content"]

    with transaction.atomic():
        conversation = get_object_or_404(
            Conversation.objects.select_for_update().filter(user=request.user), pk=conversation_id)
        if conversation.locked_at:
            flash_messages.error(request, "This conversation is locked. Unlock it before sending another message.")
            return redirect("conversations:detail", conversation_id=conversation.pk)
        if not conversation.title_is_manual and conversation.title == "New conversation" and not conversation.messages.exists():
            conversation.title = title_from_first_question(content)
            conversation.save(update_fields=("title", "updated_at"))
        Message.objects.create(conversation=conversation, role=Message.Role.USER,
                               content=content, status=Message.Status.COMPLETE)
        assistant_message = Message.objects.create(conversation=conversation, role=Message.Role.ASSISTANT,
            content="", status=Message.Status.PENDING)
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=("updated_at",))

    correlation_id = uuid.uuid4().hex
    trusted_answer = answer_creator_question(content)
    if trusted_answer is not None:
        with transaction.atomic():
            assistant_message.content = trusted_answer
            assistant_message.status = Message.Status.COMPLETE
            assistant_message.save(update_fields=("content", "status"))
            GenerationMetadata.objects.create(
                message=assistant_message,
                request_id=correlation_id,
                retrieval_mode="trusted_metadata",
                model_version=None,
                index_version=None,
                stage_timings={"trusted_metadata": 0},
                diagnostics={"answer_source": "public_creator_profile", "retrieval_performed": False},
                verification_status=GenerationMetadata.VerificationStatus.TRUSTED_METADATA,
            )
            conversation.updated_at = timezone.now()
            conversation.save(update_fields=("updated_at",))
        return redirect("conversations:detail", conversation_id=conversation.pk)

    rag_client = None
    rag_http_started = time.perf_counter()
    try:
        rag_client = get_rag_client()
        preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
        response = rag_client.query(content, top_k=settings.RAG_API_TOP_K, correlation_id=correlation_id,
                                    response_style=preferences.response_style)
    except RAGClientError as exc:
        rag_http_ms = (time.perf_counter() - rag_http_started) * 1000
        assistant_message.status = Message.Status.FAILED
        is_oversize = isinstance(exc, RAGClientInputTooLarge)
        assistant_message.content = (
            "The question leaves too little room for reference evidence in the model context. Shorten it and try again."
            if is_oversize else "The RAG service is temporarily unavailable. Please try again."
        )
        assistant_message.save(update_fields=("status", "content"))
        generation_metadata = GenerationMetadata.objects.create(
            message=assistant_message, request_id=correlation_id, retrieval_mode="",
            model_version=settings.RAG_MODEL_VERSION, index_version=settings.RAG_INDEX_VERSION,
            stage_timings={"django_rag_http": round(rag_http_ms, 3)},
            verification_status=GenerationMetadata.VerificationStatus.FAILED,
            diagnostics={"failure_code": exc.error_code, "failure_stage": exc.error_stage,
                         "http_status": exc.http_status},
        )
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=("updated_at",))
        flash_messages.error(request, assistant_message.content if is_oversize
                             else "The RAG service could not complete this message.")
        return redirect("conversations:detail", conversation_id=conversation.pk)
    finally:
        close = getattr(rag_client, "close", None)
        if callable(close):
            close()

    rag_http_ms = (time.perf_counter() - rag_http_started) * 1000
    persistence_started = time.perf_counter()
    with transaction.atomic():
        assistant_message.content = response.answer
        assistant_message.status = Message.Status.COMPLETE
        assistant_message.save(update_fields=("content", "status"))
        CitationSnapshot.objects.bulk_create([
            CitationSnapshot(
                message=assistant_message, citation_id=citation.citation_id,
                source_id=citation.source_id, document_id=citation.document_id,
                chunk_id=citation.chunk_id, title=citation.title,
                page_references=list(citation.page_references), section=citation.section,
                source_reference=citation.source_reference,
            ) for citation in response.citations
        ])
        generation_metadata = GenerationMetadata.objects.create(
            message=assistant_message, request_id=response.request_id or correlation_id,
            retrieval_mode=response.retrieval_mode, model_version=settings.RAG_MODEL_VERSION,
            index_version=settings.RAG_INDEX_VERSION,
            stage_timings={**response.stage_timings, "django_rag_http": round(rag_http_ms, 3)},
            diagnostics=response.diagnostics,
            verification_status=(GenerationMetadata.VerificationStatus.SYNTHETIC if response.synthetic
                                 else response.verification_status),
        )
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=("updated_at",))
    persistence_ms = round((time.perf_counter() - persistence_started) * 1000, 3)
    generation_metadata.stage_timings = {
        **generation_metadata.stage_timings,
        "django_persistence": persistence_ms,
    }
    generation_metadata.save(update_fields=("stage_timings",))
    return redirect("conversations:detail", conversation_id=conversation.pk)
