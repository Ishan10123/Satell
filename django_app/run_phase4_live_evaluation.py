"""Run a real 30-query Phase 4 evaluation through Django and FastAPI.

This script is copied into the existing Django container and invoked only for
the evaluation. It wraps all temporary user/conversation/message writes in one
PostgreSQL transaction and unconditionally rolls it back.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time
import uuid

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import transaction  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402

from conversations.models import CitationSnapshot, Conversation, GenerationMetadata, Message  # noqa: E402


INPUT = Path("/tmp/phase4_evaluation_questions.json")
OUTPUT = Path("/tmp/phase4_live_django_results.json")


def write_partial(rows: list[dict]) -> None:
    OUTPUT.write_text(json.dumps({"query_count": len(rows), "rows": rows}, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")


def main() -> None:
    dataset = json.loads(INPUT.read_text(encoding="utf-8"))
    queries = dataset["queries"]
    rows: list[dict] = []
    with transaction.atomic():
        try:
            user_model = get_user_model()
            user_fields = {field.name for field in user_model._meta.fields}
            username_field = user_model.USERNAME_FIELD
            identity = f"phase4-eval-{uuid.uuid4().hex}"
            create_fields = {username_field: identity}
            if "email" in user_fields and username_field != "email":
                create_fields["email"] = f"{identity}@example.invalid"
            manager = user_model._default_manager
            user = manager.create_user(password=uuid.uuid4().hex, **create_fields)
            conversation = Conversation.objects.create(user=user, title="Temporary Phase 4 evaluation")
            client = Client()
            client.force_login(user)
            post_path = reverse("conversations:message_create", kwargs={"conversation_id": conversation.pk})
            for query in queries:
                started = time.perf_counter()
                response = client.post(post_path, {"content": query["question"]}, HTTP_HOST="127.0.0.1")
                elapsed_ms = (time.perf_counter() - started) * 1000
                user_message = conversation.messages.filter(role=Message.Role.USER).order_by("-created_at").first()
                assistant = conversation.messages.filter(role=Message.Role.ASSISTANT).order_by("-created_at").first()
                if response.status_code not in {302, 303} or assistant is None:
                    row = {"query_id": query["query_id"], "http_status": response.status_code,
                           "message_status": "missing", "end_to_end_ms": round(elapsed_ms, 3),
                           "failure_category": "django_submission_or_persistence"}
                else:
                    metadata = GenerationMetadata.objects.filter(message=assistant).first()
                    citations = list(CitationSnapshot.objects.filter(message=assistant).values(
                        "citation_id", "source_id", "document_id", "chunk_id", "title", "page_references",
                        "section", "source_reference"))
                    diagnostics = metadata.diagnostics if metadata and isinstance(metadata.diagnostics, dict) else {}
                    hits = diagnostics.get("retrieval_hits", [])
                    source_ids = list(dict.fromkeys(hit.get("source_id") for hit in hits
                        if isinstance(hit, dict) and isinstance(hit.get("source_id"), str)))
                    row = {
                        "query_id": query["query_id"], "question": query["question"],
                        "expected_sources": query["expected_sources"],
                        "expected_behavior": query["expected_behavior"],
                        "http_status": response.status_code,
                        "message_status": assistant.status,
                        "answer": assistant.content,
                        "verification_status": metadata.verification_status if metadata else "not_reported",
                        "retrieval_mode": metadata.retrieval_mode if metadata else "",
                        "request_id": metadata.request_id if metadata else None,
                        "retrieval_hits": hits,
                        "retrieved_source_ids": source_ids,
                        "context_chunk_count": diagnostics.get("context_chunk_count"),
                        "context_token_estimate": diagnostics.get("context_token_estimate"),
                        "context_exclusion_reasons": diagnostics.get("context_exclusion_reasons", {}),
                        "claim_count": diagnostics.get("claim_count"),
                        "supported_claim_count": diagnostics.get("supported_claim_count"),
                        "rejected_claim_count": diagnostics.get("rejected_claim_count"),
                        "citation_validation_status": diagnostics.get("citation_validation_status"),
                        "claim_verifier_status": diagnostics.get("claim_verifier_status"),
                        "failure_code": diagnostics.get("failure_code"),
                        "failure_stage": diagnostics.get("failure_stage"),
                        "generation_model": diagnostics.get("generation_model"),
                        "citations": citations,
                        "stage_timings_ms": metadata.stage_timings if metadata else {},
                        "end_to_end_ms": round(elapsed_ms, 3),
                        "synthetic": metadata.verification_status == GenerationMetadata.VerificationStatus.SYNTHETIC
                                     if metadata else None,
                    }
                rows.append(row)
                write_partial(rows)
                print(f"django live {query['query_id']} complete; status={row.get('verification_status', row.get('failure_category'))}",
                      flush=True)
            client.logout()
        finally:
            transaction.set_rollback(True)
    write_partial(rows)
    print(f"saved {OUTPUT}; rolled back temporary Django database writes", flush=True)


if __name__ == "__main__":
    main()
