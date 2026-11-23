from datetime import timedelta
import hashlib
import ipaddress
import json
import logging
import re
import secrets
import uuid
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib import messages as flash_messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from chat.forms import MAX_MESSAGE_CHARS
from .forms import ConversationTitleForm, ShareExpirationForm
from .models import Conversation, Message

logger = logging.getLogger(__name__)


def _owned_conversation(request: HttpRequest, conversation_id: uuid.UUID) -> Conversation:
    return get_object_or_404(Conversation.objects.filter(user=request.user), pk=conversation_id)


@login_required
@require_GET
def conversation_list(request: HttpRequest) -> HttpResponse:
    conversations = Conversation.objects.filter(user=request.user).only(
        "id", "title", "created_at", "updated_at", "locked_at", "share_expires_at"
    )
    page = Paginator(conversations, 50).get_page(request.GET.get("page"))
    return render(request, "conversations/list.html", {
        "conversations_page": page,
        "conversations": page.object_list,
        "sidebar_conversations": conversations[:100],
    })


@login_required
@require_POST
def conversation_create(request: HttpRequest) -> HttpResponse:
    title = " ".join(request.POST.get("title", "").split())[:200] or "New conversation"
    conversation = Conversation.objects.create(user=request.user, title=title,
        title_is_manual=title != "New conversation")
    return redirect("conversations:detail", conversation_id=conversation.pk)


@login_required
@require_GET
def conversation_detail(request: HttpRequest, conversation_id: uuid.UUID) -> HttpResponse:
    conversation = _owned_conversation(request, conversation_id)
    return _render_conversation_detail(request, conversation)


def _render_conversation_detail(request: HttpRequest, conversation: Conversation,
                                share_link_once: str | None = None) -> HttpResponse:
    sidebar_conversations = Conversation.objects.filter(user=request.user).only(
        "id", "title", "created_at", "updated_at", "locked_at", "share_expires_at"
    )[:100]
    messages_page = Paginator(
        conversation.messages.prefetch_related("citations", "generation_metadata"), 50
    ).get_page(request.GET.get("page"))
    share_active = bool(conversation.share_token_hash and conversation.share_expires_at
                        and conversation.share_expires_at > timezone.now())
    response = render(request, "conversations/detail.html", {
        "conversation": conversation,
        "messages_page": messages_page,
        "messages_list": messages_page.object_list,
        "sidebar_conversations": sidebar_conversations,
        "adapter_mode": settings.RAG_ADAPTER,
        "max_message_chars": MAX_MESSAGE_CHARS,
        "share_link_once": share_link_once,
        "share_active": share_active,
    })
    if share_link_once:
        response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_POST
def conversation_delete(request: HttpRequest, conversation_id: uuid.UUID) -> HttpResponse:
    conversation = _owned_conversation(request, conversation_id)
    if conversation.locked_at:
        flash_messages.error(request, "Unlock this conversation before deleting it.")
        return redirect("conversations:detail", conversation_id=conversation.pk)
    title = conversation.title
    conversation.delete()
    flash_messages.success(request, f"Conversation ‘{title}’ deleted.")
    return redirect("conversations:list")


@login_required
@require_POST
def conversation_rename(request: HttpRequest, conversation_id: uuid.UUID) -> HttpResponse:
    conversation = _owned_conversation(request, conversation_id)
    form = ConversationTitleForm(request.POST)
    if form.is_valid():
        conversation.title = form.cleaned_data["title"]
        conversation.title_is_manual = True
        conversation.save(update_fields=("title", "title_is_manual", "updated_at"))
        flash_messages.success(request, "Conversation renamed.")
    else:
        flash_messages.error(request, "Enter a conversation title of 1 to 70 characters.")
    return redirect("conversations:detail", conversation_id=conversation.pk)


@login_required
@require_POST
def conversation_lock(request: HttpRequest, conversation_id: uuid.UUID) -> HttpResponse:
    conversation = _owned_conversation(request, conversation_id)
    conversation.locked_at = timezone.now()
    conversation.save(update_fields=("locked_at", "updated_at"))
    flash_messages.success(request, "Conversation locked. It is read-only until you unlock it.")
    return redirect("conversations:detail", conversation_id=conversation.pk)


@login_required
@require_POST
def conversation_unlock(request: HttpRequest, conversation_id: uuid.UUID) -> HttpResponse:
    conversation = _owned_conversation(request, conversation_id)
    conversation.locked_at = None
    conversation.save(update_fields=("locked_at", "updated_at"))
    flash_messages.success(request, "Conversation unlocked.")
    return redirect("conversations:detail", conversation_id=conversation.pk)


def _public_citation(citation):
    import html
    title = html.unescape(re.sub(r"\s*\{\s*#\s*[A-Za-z0-9_-]+\s*\}", "", citation.title or ""))
    title = " ".join(title.split()) or "Source document"
    section = html.unescape(re.sub(r"\s*\{\s*#\s*[A-Za-z0-9_-]+\s*\}", "", citation.section or ""))
    section = " ".join(section.split())
    if section.casefold() == title.casefold():
        section = ""
    reference = citation.source_reference or ""
    parsed = urlsplit(reference)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        reference = ""
    else:
        host = parsed.hostname.lower()
        try:
            if not ipaddress.ip_address(host).is_global:
                reference = ""
        except ValueError:
            if host == "localhost" or "." not in host:
                reference = ""
    if reference:
        from urllib.parse import urlunsplit
        reference = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return {"citation_id": citation.citation_id, "title": title, "section": section,
            "page_references": citation.page_references or [], "source_reference": reference}


@login_required
@require_GET
def conversation_export(request: HttpRequest, conversation_id: uuid.UUID, format: str) -> HttpResponse:
    conversation = get_object_or_404(Conversation.objects.filter(user=request.user), pk=conversation_id)
    if format not in {"md", "txt", "json"}:
        raise Http404
    rows = []
    messages_qs = conversation.messages.prefetch_related("citations", "generation_metadata").order_by("created_at", "id")
    for message in messages_qs:
        metadata = next(iter(message.generation_metadata.all()), None)
        rows.append({
            "role": "You" if message.role == Message.Role.USER else "Satell",
            "content": message.content,
            "created_at": message.created_at.isoformat(),
            "verification_status": metadata.verification_status if metadata else "not_reported",
            "citations": [_public_citation(citation) for citation in message.citations.all()],
        })
    created = conversation.created_at.isoformat()
    updated = conversation.updated_at.isoformat()
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", conversation.title).strip("-")[:60] or "conversation"
    if format == "json":
        body = json.dumps({"title": conversation.title, "created_at": created,
            "updated_at": updated, "messages": rows}, ensure_ascii=False, indent=2)
        content_type, extension = "application/json; charset=utf-8", "json"
    elif format == "txt":
        lines = [conversation.title, f"Created: {created}", f"Updated: {updated}", ""]
        for row in rows:
            lines.extend([f"{row['role']} — {row['created_at']}", row["content"],
                          f"Verification: {row['verification_status']}"])
            for citation in row["citations"]:
                lines.append(f"{citation['citation_id']} — {citation['title']}" +
                    (f" — {citation['source_reference']}" if citation["source_reference"] else ""))
            lines.append("")
        body, content_type, extension = "\n".join(lines), "text/plain; charset=utf-8", "txt"
    else:
        lines = [f"# {conversation.title}", "", f"Created: {created}", f"Updated: {updated}", ""]
        for row in rows:
            lines.extend([f"## {row['role']}", "", row["content"], "",
                          f"Verification status: `{row['verification_status']}`", ""])
            for citation in row["citations"]:
                label = f"{citation['citation_id']} — {citation['title']}"
                if citation["section"]:
                    label += f" — {citation['section']}"
                if citation["source_reference"]:
                    label = f"[{label}]({citation['source_reference']})"
                lines.append(f"- {label}")
            lines.append("")
        body, content_type, extension = "\n".join(lines), "text/markdown; charset=utf-8", "md"
    response = HttpResponse(body, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{stem}.{extension}"'
    response["Cache-Control"] = "no-store"
    return response


@login_required
@require_POST
def conversation_share_create(request: HttpRequest, conversation_id: uuid.UUID) -> HttpResponse:
    conversation = _owned_conversation(request, conversation_id)
    form = ShareExpirationForm(request.POST)
    if not form.is_valid():
        flash_messages.error(request, "Choose a share expiration between 1 and 30 days.")
        return redirect("conversations:detail", conversation_id=conversation.pk)
    token = secrets.token_urlsafe(32)
    conversation.share_token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    conversation.share_expires_at = timezone.now() + timedelta(days=form.cleaned_data["expiration_days"])
    conversation.save(update_fields=("share_token_hash", "share_expires_at", "updated_at"))
    share_link = settings.PUBLIC_APP_BASE_URL + reverse("conversations:shared", kwargs={"token": token})
    return _render_conversation_detail(request, conversation, share_link_once=share_link)


@login_required
@require_POST
def conversation_share_revoke(request: HttpRequest, conversation_id: uuid.UUID) -> HttpResponse:
    conversation = _owned_conversation(request, conversation_id)
    conversation.share_token_hash = ""
    conversation.share_expires_at = None
    conversation.save(update_fields=("share_token_hash", "share_expires_at", "updated_at"))
    flash_messages.success(request, "Conversation share link revoked.")
    return redirect("conversations:detail", conversation_id=conversation.pk)


@never_cache
@require_GET
def conversation_shared(request: HttpRequest, token: str) -> HttpResponse:
    if not 32 <= len(token) <= 128:
        raise Http404
    address = request.META.get("REMOTE_ADDR", "unknown")
    rate_key = "satell:share:" + hashlib.sha256(address.encode("utf-8")).hexdigest()
    try:
        if not cache.add(rate_key, 1, 60) and cache.incr(rate_key) > 60:
            return HttpResponse("Too many requests.", status=429)
    except Exception:
        logger.error("Share-link request throttling unavailable; request rejected.")
        return HttpResponse("Temporarily unavailable.", status=503)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    conversation = Conversation.objects.filter(share_token_hash=token_hash,
        share_expires_at__gt=timezone.now()).first()
    if conversation is None:
        raise Http404
    source_messages = conversation.messages.filter(status=Message.Status.COMPLETE).prefetch_related(
        "citations", "generation_metadata").order_by("created_at", "id")
    messages_list = [{
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at,
        "verification_status": next(iter(message.generation_metadata.all()), None),
        "citations": [_public_citation(citation) for citation in message.citations.all()],
    } for message in source_messages]
    for row in messages_list:
        row["verification_status"] = getattr(row["verification_status"], "verification_status", "not_reported")
    response = render(request, "conversations/shared.html", {
        "conversation": conversation, "messages_list": messages_list,
    })
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["Cache-Control"] = "private, no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response
