"""Synthetic-only HTTP fixture for Django integration tests; has no RAG imports."""

import hmac
import os
import re

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field


TOKEN = os.environ.get("RAG_SYNTHETIC_TEST_TOKEN", "")
if len(TOKEN) < 32:
    raise RuntimeError("Synthetic fixture token must contain at least 32 characters.")

app = FastAPI(title="Synthetic RAG Contract Fixture", docs_url=None, redoc_url=None, openapi_url=None)


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=5000)
    top_k: int = Field(default=8, ge=1, le=20)


@app.get("/health")
def health():
    return {"status": "ok", "synthetic": True}


@app.post("/v1/query")
def query(body: QueryRequest, authorization: str = Header(default=""), x_correlation_id: str = Header(default="")):
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(credential, TOKEN):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials.")
    request_id = x_correlation_id if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", x_correlation_id) else "synthetic-request"
    return {
        "answer": "Synthetic integration response only; this is not a real RAG result.",
        "citations": [{
            "citation_id": "S1", "source_id": "synthetic_source",
            "document_id": "synthetic-document", "chunk_id": "synthetic-chunk",
            "title": "Synthetic integration citation", "page_references": [],
            "section": "Synthetic fixture", "source_reference": "",
        }],
        "request_id": request_id,
        "retrieval_mode": "synthetic_integration_fixture",
        "timings_ms": {"fixture": 0},
        "synthetic": True,
    }
