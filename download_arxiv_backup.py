
import arxiv
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(r"E:\RAG_Project")
PAPERS_ROOT = ROOT / "knowledge_base" / "raw" / "research_papers"
METADATA_FILE = ROOT / "knowledge_base" / "metadata" / "arxiv_documents.jsonl"
FAILURE_FILE = ROOT / "knowledge_base" / "logs" / "arxiv_failures.jsonl"

LIMIT_PER_QUERY = 3
MIN_PDF_SIZE = 1024
DOWNLOAD_RETRIES = 3

QUERIES = {
    "information_retrieval": "cat:cs.IR AND (all:retrieval OR all:ranking OR all:search)",
    "llm_rag": "cat:cs.CL AND (all:RAG OR all:LLM OR all:language model)",
    "machine_learning": "cat:cs.LG AND (all:embedding OR all:inference OR all:transformer)"
}

client = arxiv.Client(
    page_size=50,
    delay_seconds=3,
    num_retries=5
)

PAPERS_ROOT.mkdir(parents=True, exist_ok=True)
METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
FAILURE_FILE.parent.mkdir(parents=True, exist_ok=True)


def canonical_id(entry_id):
    paper_id = entry_id.rsplit("/", 1)[-1]
    return re.sub(r"v\d+$", "", paper_id)


def safe_filename(paper_id):
    return re.sub(r"[^A-Za-z0-9._-]", "_", paper_id)


def is_valid_pdf(path):
    if not path.exists() or path.stat().st_size < MIN_PDF_SIZE:
        return False

    with path.open("rb") as file:
        return file.read(5) == b"%PDF-"


def calculate_sha256(path):
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def download_pdf(pdf_url, output_path):
    if not pdf_url:
        raise ValueError("PDF URL is missing")

    request = Request(
        pdf_url,
        headers={
            "User-Agent": "IshanRAGResearchCollector/1.0"
        }
    )

    last_error = None

    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        try:
            with urlopen(request, timeout=90) as response:
                with output_path.open("wb") as file:
                    while True:
                        chunk = response.read(1024 * 1024)

                        if not chunk:
                            break

                        file.write(chunk)

            if not is_valid_pdf(output_path):
                raise ValueError("Downloaded file failed PDF validation")

            return

        except Exception as error:
            last_error = error

            if output_path.exists():
                output_path.unlink()

            if attempt < DOWNLOAD_RETRIES:
                time.sleep(attempt * 5)

    raise RuntimeError(
        f"PDF download failed after {DOWNLOAD_RETRIES} attempts: {last_error}"
    )


def load_completed_ids():
    completed = set()

    if not METADATA_FILE.exists():
        return completed

    with METADATA_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            try:
                record = json.loads(line)
                path = Path(record["local_path"])
                paper_id = record["arxiv_id"]

                if record.get("downloaded") and is_valid_pdf(path):
                    completed.add(paper_id)

            except (json.JSONDecodeError, KeyError, OSError, TypeError):
                continue

    return completed


def write_jsonl(path, record):
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    completed_ids = load_completed_ids()
    attempted_ids = set()

    print(f"Previously completed papers: {len(completed_ids)}")

    for category, query in QUERIES.items():
        output_dir = PAPERS_ROOT / category
        output_dir.mkdir(parents=True, exist_ok=True)

        search = arxiv.Search(
            query=query,
            max_results=LIMIT_PER_QUERY,
            sort_by=arxiv.SortCriterion.Relevance
        )

        print(f"\nCollecting category: {category}")

        try:
            for result in client.results(search):
                paper_id = canonical_id(result.entry_id)

                if paper_id in completed_ids or paper_id in attempted_ids:
                    continue

                attempted_ids.add(paper_id)

                filename = safe_filename(paper_id)
                output_path = output_dir / f"{filename}.pdf"
                temporary_path = output_dir / f"{filename}.download.pdf"

                try:
                    if not is_valid_pdf(output_path):
                        if output_path.exists():
                            output_path.unlink()

                        download_pdf(result.pdf_url, temporary_path)
                        os.replace(temporary_path, output_path)

                    record = {
                        "arxiv_id": paper_id,
                        "versioned_id": result.entry_id.rsplit("/", 1)[-1],
                        "title": result.title,
                        "abstract": result.summary,
                        "authors": [author.name for author in result.authors],
                        "published": result.published.isoformat(),
                        "updated": result.updated.isoformat(),
                        "primary_category": result.primary_category,
                        "categories": result.categories,
                        "source_url": result.entry_id,
                        "pdf_url": result.pdf_url,
                        "local_path": str(output_path),
                        "file_size_bytes": output_path.stat().st_size,
                        "sha256": calculate_sha256(output_path),
                        "downloaded_at": datetime.now(timezone.utc).isoformat(),
                        "downloaded": True,
                        "collection": category
                    }

                    write_jsonl(METADATA_FILE, record)
                    completed_ids.add(paper_id)

                    print(f"Downloaded: {paper_id} | {result.title}")

                except Exception as error:
                    failure = {
                        "arxiv_id": paper_id,
                        "title": result.title,
                        "collection": category,
                        "error": str(error),
                        "failed_at": datetime.now(timezone.utc).isoformat()
                    }

                    write_jsonl(FAILURE_FILE, failure)
                    print(f"Failed: {paper_id} | {error}")

                finally:
                    if temporary_path.exists():
                        temporary_path.unlink()

                time.sleep(3)

        except Exception as error:
            print(f"Category search failed: {category} | {error}")

    print("\nCollection run completed.")
    print(f"Successfully collected papers: {len(completed_ids)}")
    print(f"Metadata: {METADATA_FILE}")
    print(f"Failure log: {FAILURE_FILE}")


if __name__ == "__main__":
    main()
