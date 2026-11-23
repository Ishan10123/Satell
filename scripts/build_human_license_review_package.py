"""Build a human-review-only license packet; never writes approval registries."""
from __future__ import annotations

import argparse
import csv
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / "knowledge_base" / "metadata"
NOW = datetime.now(timezone.utc).isoformat()
DATE = NOW[:10]

SOURCE_INFO = {
    "docker": {"name": "Docker documentation", "official_url": "https://docs.docker.com/", "repo": "https://github.com/docker/docs.git", "license": "Apache-2.0", "license_url": "https://github.com/docker/docs/blob/553482ce632f00c6e7faabab863422b4916e7c18/docs/LICENSE", "status": "Evidence exists but scope is incomplete", "scope": "The repository contains a docs/LICENSE artifact. Review its exact pinned revision, examples, third-party snippets, images and notices individually.", "third_party": "Documentation has code samples, diagrams, screenshots, product marks and bundled assets; repository-level license does not establish the license of each asset."},
    "fastapi": {"name": "FastAPI documentation", "official_url": "https://fastapi.tiangolo.com/", "repo": "https://github.com/fastapi/fastapi.git", "license": "MIT (repository metadata; documentation-specific scope not independently established)", "license_url": "https://github.com/fastapi/fastapi/blob/5758a9c8347d911444dca97a55b708cc4a8de4f8/LICENSE", "status": "Evidence exists but scope is incomplete", "scope": "A repository MIT license exists at the pinned source revision; inspect each documentation asset and code sample provenance.", "third_party": "Interactive API documentation, icons, external projects and embedded examples may have separate terms."},
    "huggingface_transformers": {"name": "Hugging Face Transformers documentation", "official_url": "https://huggingface.co/docs/transformers/", "repo": "https://github.com/huggingface/transformers.git", "license": "Apache-2.0 (repository license; documentation scope requires review)", "license_url": "https://github.com/huggingface/transformers/blob/3a134bc37f7c22c801b618e289b0255425f22647/LICENSE", "status": "Evidence exists but scope is incomplete", "scope": "Pinned repository license is Apache-2.0; confirm which documentation text/examples are contributed or generated and inspect referenced assets.", "third_party": "Model examples, datasets, external model cards, badges, figures and third-party components may carry independent terms."},
    "postgresql_18": {"name": "PostgreSQL 18 documentation", "official_url": "https://www.postgresql.org/docs/18/", "repo": None, "license": "PostgreSQL License (official project states it covers software and documentation)", "license_url": "https://www.postgresql.org/about/licence/", "status": "Evidence verified and scope sufficiently documented for human consideration", "scope": "The official license page expressly includes documentation. Reviewer should check notices and attributed third-party excerpts in the specific PDF edition.", "third_party": "PDF figures, cited extracts, trademarks and any externally credited material remain subject to their own terms."},
    "python_3_13": {"name": "Python 3.13 documentation", "official_url": "https://docs.python.org/3.13/", "repo": None, "license": "PSF License Version 2; examples and recipes additionally Zero Clause BSD", "license_url": "https://docs.python.org/3.13/copyright.html", "status": "Evidence verified and scope sufficiently documented for human consideration", "scope": "The official copyright page distinguishes the main docs from code examples. Confirm use of examples fits their additional license and inspect included third-party content.", "third_party": "Third-party libraries, logos, screenshots, fonts and copied examples can have separate rights."},
    "pytorch": {"name": "PyTorch documentation", "official_url": "https://pytorch.org/docs/stable/", "repo": "https://github.com/pytorch/pytorch.git", "license": "PyTorch docs repository states BSD; local PyTorch repository also contains multiple third-party licenses", "license_url": "https://github.com/pytorch/docs", "status": "Evidence exists but scope is incomplete", "scope": "The separate pytorch/docs project states its docs are BSD licensed. Local source inventory includes PyTorch LICENSE and NOTICE, which cover a larger code repository with multiple dependency licenses; do not use those as blanket docs evidence.", "third_party": "Tutorial/code examples, embedded project names, dependencies, generated API content and media require separate attribution and license review."},
    "qdrant": {"name": "Qdrant documentation", "official_url": "https://qdrant.tech/documentation/", "repo": "https://github.com/qdrant/landing_page.git", "license": None, "license_url": "https://github.com/qdrant/landing_page/blob/799edaa9d0ef562790402d6d4ddf370db92162e5/LICENSE", "status": "Not enough evidence to recommend approval", "scope": "The pinned repository LICENSE URL returned 404 and no local Qdrant license artifact is cataloged. Request an authoritative docs/content license or written permission.", "third_party": "Docs include code examples, diagrams, customer logos and externally linked material; all need scope/attribution review."},
}


class LicenseLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.license_href = None
        self.title = None
        self._title = False
        self._title_parts = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and (a.get("title") == "Rights to this article" or "license" in (a.get("class") or "").lower()):
            self.license_href = a.get("href")
        if tag == "title":
            self._title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._title = False
            self.title = " ".join("".join(self._title_parts).split())

    def handle_data(self, data):
        if self._title:
            self._title_parts.append(data)


def jsonl(path: Path):
    with path.open(encoding="utf-8-sig") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def license_name_from_text(text: str | None):
    if not text:
        return None
    if "Apache License" in text or "Apache-2.0" in text:
        return "Apache-2.0"
    if "MIT License" in text or "Permission is hereby granted, free of charge" in text:
        return "MIT"
    if "BSD 3-Clause" in text:
        return "BSD-3-Clause"
    if "BSD 2-Clause" in text:
        return "BSD-2-Clause"
    return None


def fetch_arxiv_page(record):
    arxiv_id = record["arxiv_id"]
    url = f"https://arxiv.org/abs/{arxiv_id}"
    try:
        req = Request(url, headers={"User-Agent": "RAG-Project-human-license-review/1.0 (local evidence preparation)"})
        with urlopen(req, timeout=25) as response:
            body = response.read(1_500_000).decode("utf-8", errors="replace")
        parser = LicenseLinkParser()
        parser.feed(body)
        return arxiv_id, {"url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                          "http_status": 200, "page_title": parser.title, "license_url": parser.license_href,
                          "retrieval_status": "rights_link_found" if parser.license_href else "no_rights_link_found"}
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError) as exc:
        return arxiv_id, {"url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                          "http_status": getattr(exc, "code", None), "license_url": None,
                          "retrieval_status": "retrieval_failed", "error": str(exc)[:300]}


def pdf_rights_snippets(path: Path):
    if not path.is_file():
        return []
    patterns = re.compile(r"creative commons|\bCC\s*BY(?:-[A-Z]+)*\b|copyright.{0,100}|licensed under.{0,100}|all rights reserved", re.I)
    try:
        reader = PdfReader(str(path), strict=False)
        text = "\n".join((reader.pages[i].extract_text() or "") for i in range(min(2, len(reader.pages))))
        return [" ".join(m.group(0).split())[:220] for m in patterns.finditer(text)][:5]
    except Exception:
        return []


def arxiv_license_class(url: str | None):
    if not url:
        return "License or rights information missing"
    value = url.casefold()
    if "nonexclusive-distrib" in value:
        return "Not enough evidence to recommend approval"
    if "creativecommons.org/publicdomain/zero" in value or "cc0" in value:
        return "Evidence verified and scope sufficiently documented for human consideration"
    if "creativecommons.org/licenses/by/" in value:
        return "Evidence verified and scope sufficiently documented for human consideration"
    if "creativecommons.org/licenses/by-sa/" in value:
        return "Evidence exists but scope is incomplete"
    if "by-nc" in value or "by-nd" in value:
        return "Evidence exists but scope is incomplete"
    return "Evidence exists but scope is incomplete"


def arxiv_license_name(url: str | None):
    if not url:
        return None
    value = url.casefold()
    if "nonexclusive-distrib" in value:
        return "arXiv non-exclusive distribution license (limited distribution grant)"
    match = re.search(r"creativecommons\.org/licenses/([^/]+)/(\d+(?:\.\d+)*)", value)
    if match:
        return f"CC {match.group(1).upper()} {match.group(2)}"
    if "creativecommons.org/publicdomain/zero" in value or "cc0" in value:
        return "CC0"
    return url.rsplit("/", 1)[-1].strip() or url


def build(fetch_arxiv: bool):
    approvals = json.loads((META / "source_approvals.json").read_text(encoding="utf-8-sig"))
    inventory = list(jsonl(META / "ingestion_inventory.jsonl"))
    metadata = list(jsonl(META / "arxiv_documents.jsonl"))
    audits = {r["arxiv_id"]: r for r in jsonl(META / "arxiv_audit_report.jsonl")}
    evidence_rows = list(jsonl(META / "license_evidence.jsonl"))
    repo_rows = {}
    for row in jsonl(META / "documentation_manifest.jsonl"):
        sid = row.get("source_id")
        if sid and sid not in repo_rows:
            repo_rows[sid] = {"repository": row.get("repository"), "commit": row.get("source_commit"), "website": row.get("source_url")}
    source_ids = set(approvals["sources"])
    source_docs = {s: [] for s in source_ids}
    for row in inventory:
        source_docs.setdefault(row.get("source_id"), []).append(row)

    # Retrieve individual arXiv abstract/license-link metadata; this does not infer
    # permission from article availability and does not change an approval record.
    fetched = {}
    if fetch_arxiv:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(fetch_arxiv_page, r) for r in metadata]
            for future in as_completed(futures):
                paper_id, result = future.result()
                fetched[paper_id] = result
    papers = []
    for item in metadata:
        aid = item["arxiv_id"]
        audit = audits.get(aid, {})
        page = fetched.get(aid, {"url": f"https://arxiv.org/abs/{aid}", "retrieved_at": None,
                                  "http_status": None, "license_url": None, "retrieval_status": "not_retrieved"})
        path = Path(item.get("local_path", ""))
        actual_hash = sha256(path) if path.is_file() else None
        expected_hash = item.get("sha256")
        rights_uri = page.get("license_url")
        rights_class = arxiv_license_class(rights_uri) if page.get("http_status") == 200 else "License or rights information missing"
        if rights_uri and "nonexclusive-distrib" in rights_uri:
            rights_note = "arXiv's selected non-exclusive distribution license grants arXiv distribution rights; arXiv's policy describes limited reuse rights for other parties. This is not evidence of general reuse permission."
        elif rights_uri:
            rights_note = "A paper-specific license URI is present; reviewer must inspect its exact terms, version, author rights, publisher obligations, and third-party figures/data."
        else:
            rights_note = "No paper-specific license URI was retrieved; inspect the abstract page and PDF front matter manually."
        paper = {
            "source_id": f"arxiv_{item.get('collection', 'unknown')}",
            "document_id": hashlib.sha256(f"arxiv_{item.get('collection','unknown')}\0{expected_hash or ''}".encode()).hexdigest(),
            "arxiv_id": aid, "versioned_id": item.get("versioned_id"), "title": item.get("title"),
            "authors": item.get("authors", []), "published": item.get("published"), "updated": item.get("updated"),
            "collection": item.get("collection"), "local_path": str(path), "pdf_url": item.get("pdf_url"),
            "abstract_url": page["url"], "metadata_source_url": item.get("source_url"),
            "license_url": rights_uri, "license_name": arxiv_license_name(rights_uri),
            "license_evidence_status": rights_class, "rights_information": rights_note,
            "evidence_retrieval_status": page.get("retrieval_status"), "evidence_retrieved_at": page.get("retrieved_at"),
            "evidence_http_status": page.get("http_status"), "arxiv_pdf_audit_status": audit.get("status"),
            "pdf_checksum_status": "matches metadata" if actual_hash and actual_hash == expected_hash else "missing or mismatch",
            "pdf_front_matter_rights_snippets": pdf_rights_snippets(path),
            "rights_sufficient_for_intended_use": "manual review required; no automated permission conclusion",
            "reviewer_decision": "pending_review", "reviewer": None, "reviewed_at": None, "notes": None,
            "manual_review_required": rights_class in {"Not enough evidence to recommend approval", "License or rights information missing"},
        }
        papers.append(paper)

    source_review = []
    evidence_inventory = []
    for sid, approval in sorted(approvals["sources"].items()):
        info = SOURCE_INFO.get(sid, {"name": sid, "official_url": None, "repo": None, "license": None, "license_url": None,
            "status": "Not enough evidence to recommend approval", "scope": "No source-specific evidence record is available.", "third_party": "Unknown; review required."})
        local_paths = []
        source_root_names = {sid, sid.removeprefix("arxiv_")}
        for ev in evidence_rows:
            if ev.get("source_id") == sid:
                p = Path(ev.get("path", ""))
                exists = p.is_file()
                digest = sha256(p) if exists else None
                local_paths.append({"path": str(p), "exists": exists, "sha256_recorded": ev.get("sha256"),
                                    "sha256_actual": digest, "checksum_matches": bool(exists and digest == ev.get("sha256")),
                                    "evidence_status": ev.get("evidence_status"), "location": ev.get("location")})
        docsroot = ROOT / "knowledge_base" / "raw" / "official_documentation"
        # Record only legal/rights-named files scoped to the corresponding corpus directory.
        if sid in {"docker", "fastapi", "huggingface_transformers", "pytorch", "qdrant"}:
            source_folder = {"docker":"docker", "fastapi":"fastapi", "huggingface_transformers":"huggingface_transformers", "pytorch":"pytorch", "qdrant":"qdrant"}[sid]
            local_root = docsroot / source_folder
        elif sid == "python_3_13":
            local_root = docsroot / "python" / "3.13" / "python-3.13-docs-html"
        elif sid == "postgresql_18":
            local_root = docsroot / "postgresql"
        else:
            local_root = docsroot
        legal_files = []
        if local_root.exists():
            for file in local_root.rglob("*"):
                if file.is_file() and any(word in file.name.casefold() for word in ("license", "licence", "notice", "copyright")):
                    rel = file.relative_to(ROOT).as_posix()
                    if file.stat().st_size <= 5_000_000:
                        digest = sha256(file)
                        legal_files.append({"path": rel, "size_bytes": file.stat().st_size, "sha256": digest,
                                            "license_name_guess": license_name_from_text(file.read_text(encoding="utf-8", errors="replace") if file.suffix.lower() in {".html", ".md", ".txt", ".rst"} else None)})
        repo = repo_rows.get(sid, {})
        review = {
            "source_id": sid, "source_name": info["name"], "source_type": "documentation_source",
            "decision_status": approval.get("status", "pending_review"), "inventory_record_count": len(source_docs.get(sid, [])),
            "repository": repo.get("repository") or info.get("repo"), "recorded_commit": repo.get("commit"),
            "official_documentation_url": repo.get("website") or info.get("official_url"),
            "official_license_evidence_url": info.get("license_url"), "retrieved_at": DATE if info.get("license_url") else None,
            "reported_license": info.get("license"), "evidence_classification": info.get("status"),
            "scope_assessment": info.get("scope"), "third_party_concerns": info.get("third_party"),
            "evidence_artifacts": local_paths, "local_legal_files": legal_files,
            "missing_evidence": [] if local_paths or legal_files or info.get("license_url") else ["No local or authoritative license evidence located."],
            "recommended_action": "Review the exact pinned-source license and documentation scope; identify third-party assets/examples and any notices; then decide approved, rejected, or pending. Do not infer blanket coverage from a repository root license.",
            "human_decision": "pending_review", "reviewer": None, "reviewed_at": None, "notes": None,
        }
        source_review.append(review)
        evidence_inventory.append({"source_id": sid, "local_evidence": local_paths, "local_legal_files": legal_files,
                                   "official_reference": {"url": info.get("license_url"), "retrieved_at": DATE if info.get("license_url") else None,
                                                          "status": "404 at pinned LICENSE URL" if sid == "qdrant" else "reference recorded for human verification"},
                                   "classification": info.get("status"), "scope": info.get("scope")})

    global_evidence = [{"kind": "arXiv policy", "url": "https://info.arxiv.org/help/license/index.html", "retrieved_at": DATE,
        "finding": "arXiv records per-version licenses chosen by the submitter; its non-exclusive distribution license grants arXiv a distribution permission and does not itself establish broad reuse rights for others. Versions can have different licenses."},
        {"kind": "arXiv metadata API documentation", "url": "https://info.arxiv.org/help/api/basics.html", "retrieved_at": DATE,
         "finding": "Official API documents programmatic metadata retrieval; metadata availability does not grant article reuse rights."}]
    evidence_inventory.append({"kind": "global_policy", "references": global_evidence})

    packet = {"report_version": "1.0", "generated_at": NOW, "project_root": str(ROOT),
              "approval_registry": "knowledge_base/metadata/source_approvals.json", "approvals_modified": False,
              "source_count": len(source_review), "arxiv_paper_count": len(papers), "sources": source_review,
              "arxiv_papers": papers, "global_policy_evidence": global_evidence,
              "note": "Evidence classifications are reviewer aids, not legal conclusions or approval decisions."}
    (META / "license_human_review_packet_20261116.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (META / "license_evidence_inventory_20261116.json").write_text(json.dumps({"report_version":"1.0","generated_at":NOW,"sources":evidence_inventory,"approvals_modified":False}, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")

    columns = ["Source ID","Source name","Document ID","Paper title","arXiv ID","Authors","Published/version","Local path","Evidence path","Evidence URL","License name","Checksum status","Evidence status","Scope","Third-party content concerns","Missing evidence","Recommended next action","Human decision","Reviewer","Review date","Notes"]
    with (META / "license_human_review_checklist_20261116.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=columns,extrasaction="ignore");writer.writeheader()
        for row in source_review:
            writer.writerow({"Source ID":row["source_id"],"Source name":row["source_name"],"Evidence path":"; ".join(x["path"] for x in row["evidence_artifacts"]+row["local_legal_files"]),"Evidence URL":row["official_license_evidence_url"],"License name":row["reported_license"],"Checksum status":"; ".join("match" if x["checksum_matches"] else "missing/mismatch" for x in row["evidence_artifacts"]) or "not cataloged", "Evidence status":row["evidence_classification"],"Scope":row["scope_assessment"],"Third-party content concerns":row["third_party_concerns"],"Missing evidence":"; ".join(row["missing_evidence"]),"Recommended next action":row["recommended_action"],"Human decision":"pending_review"})
        for row in papers:
            writer.writerow({"Source ID":row["source_id"],"Source name":"arXiv paper","Document ID":row["document_id"],"Paper title":row["title"],"arXiv ID":row["arxiv_id"],"Authors":"; ".join(row["authors"]),"Published/version":f"{row['published']} / {row['versioned_id']}","Local path":row["local_path"],"Evidence URL":row["license_url"] or row["abstract_url"],"License name":row["license_name"],"Checksum status":row["pdf_checksum_status"],"Evidence status":row["license_evidence_status"],"Scope":row["rights_information"],"Third-party content concerns":"Figures, tables, datasets and publisher content may have separate rights.","Missing evidence":"Per-version license details need human verification" if row["manual_review_required"] else "Check PDF and publisher/funder terms", "Recommended next action":"Open the individual arXiv page and selected license URL; compare version and PDF rights notices; check journal/funder rights and third-party figures before deciding.","Human decision":"pending_review"})

    guide = fr"""# Human license review guide

Generated {DATE}. This packet prepares evidence for the project owner; it does not make legal determinations. **All 14 source decisions remain `pending_review`.** No approval command was run and no approval registry was edited.

## Read the package

- `knowledge_base/metadata/license_human_review_checklist_20261116.csv`: Excel-friendly checklist, one row for each of the 14 source records (7 documentation sources and 7 arXiv collections), plus each of 107 individual arXiv papers.
- `knowledge_base/metadata/license_human_review_packet_20261116.json`: complete source and paper records, evidence classifications, local paths, hashes, rights URLs and retrieval status.
- `knowledge_base/metadata/license_evidence_inventory_20261116.json`: local and online evidence artifact inventory.
- `knowledge_base/metadata/source_approvals.json`: authoritative decision registry; it remains unchanged and pending.

Start with read-only reports:

```powershell
.\.venv\Scripts\python.exe scripts/ragctl.py license-report
.\.venv\Scripts\python.exe scripts/ragctl.py authorization-report
```

For each documentation source, inspect the pinned commit, recorded local legal artifacts and the official license link. Determine whether permission covers docs prose, examples/code, diagrams/media, third-party snippets, and supporting files. A root license alone is not blanket permission for third-party material. For arXiv, open each paper's individual abstract and selected license URL; distinguish the submitter's arXiv distribution license from rights to reuse text in this local RAG corpus. The arXiv page states versions can have different licenses and warns authors about journal/funder obligations. The local packet records the exact page retrieval date and failures; a failed fetch stays missing evidence.

## Decision rules

Use the packet's classifications only as review aids. `Evidence verified and scope sufficiently documented for human consideration` still requires the owner to read the exact terms and check the intended local storage, chunking, retrieval, citation, and retention use. If license identity, version, scope, third-party ownership, or intended-use compatibility is unclear, leave `pending_review` and obtain more evidence. Record one decision per documentation source, and one decision per arXiv document. Source metadata approval never approves papers.

After reviewing a documentation source, record the owner's decision with an in-project evidence catalog and accurate reviewer details, for example:

```powershell
.\.venv\Scripts\python.exe scripts/ragctl.py approve-source fastapi `
  --decision approved --reviewer "<owner name>" --license-name "MIT" `
  --scope documentation_candidates `
  --evidence knowledge_base\\metadata\\license_evidence.jsonl `
  --notes "<scope and third-party review actually completed>"
```

For an arXiv paper, first establish metadata-source scope if required by the CLI workflow, then decide the exact paper using its `document_id` from the checklist:

```powershell
.\.venv\Scripts\python.exe scripts/ragctl.py approve-document <document_id> `
  --source-id arxiv_<collection> --decision approved --reviewer "<owner name>" `
  --license-name "<verified license>" --evidence knowledge_base\\metadata\\license_evidence.jsonl `
  --notes "<paper-specific rights and third-party review completed>"
```

Do not copy placeholder values or choose `approved` unless the owner has completed that review. The commands above are procedural examples only and were not executed.

## Source review notes

""" + "\n".join(f"### {r['source_name']} (`{r['source_id']}`)\n\n- Evidence class: **{r['evidence_classification']}**.\n- Official reference: {r['official_license_evidence_url'] or 'not located'}.\n- Scope question: {r['scope_assessment']}\n- Third-party check: {r['third_party_concerns']}\n" for r in source_review) + "\n## arXiv review notes\n\nThere are 107 paper-specific rows. arXiv says each submitter chooses a license, different versions can have different licenses, and the arXiv non-exclusive license grants arXiv a limited distribution right; that link alone does not grant broad reuse permission to other users. Verify the per-paper selected URI and the first-page copyright/license text. Check publisher/funder restrictions and third-party figures/tables. Keep each paper pending when rights remain unclear.\n"
    (ROOT / "docs" / "license_human_review_guide.md").write_text(guide,encoding="utf-8")
    return {"sources":len(source_review),"papers":len(papers),"rows":len(source_review)+len(papers),"fetched_pages":sum(1 for v in fetched.values() if v.get("http_status")==200),"approval_states_unchanged":all(v.get("status")=="pending_review" for v in approvals["sources"].values())}


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-arxiv-web-fetch",action="store_true")
    args=parser.parse_args()
    print(json.dumps(build(not args.skip_arxiv_web_fetch),indent=2))
