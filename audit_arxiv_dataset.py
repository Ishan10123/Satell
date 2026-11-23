
import hashlib
import json
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(r"E:\RAG_Project")
METADATA_FILE = ROOT / "knowledge_base" / "metadata" / "arxiv_documents.jsonl"
REPORT_FILE = ROOT / "knowledge_base" / "metadata" / "arxiv_audit_report.jsonl"


def calculate_sha256(path):
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def load_metadata():
    records = []

    with METADATA_FILE.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, 1):
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                print(f"Invalid JSON at line {line_number}: {error}")

    return records


def audit_document(record):
    path = Path(record["local_path"])

    result = {
        "arxiv_id": record["arxiv_id"],
        "title": record["title"],
        "local_path": str(path),
        "status": "PASS",
        "page_count": 0,
        "text_characters": 0,
        "pages_with_text": 0,
        "sha256_valid": False,
        "warnings": []
    }

    if not path.exists():
        result["status"] = "FAIL"
        result["warnings"].append("PDF file missing")
        return result

    try:
        if path.stat().st_size < 1024:
            raise ValueError("PDF file is unexpectedly small")

        with path.open("rb") as file:
            if file.read(5) != b"%PDF-":
                raise ValueError("Invalid PDF header")

        actual_hash = calculate_sha256(path)
        expected_hash = record.get("sha256")

        result["sha256_valid"] = actual_hash == expected_hash

        if not result["sha256_valid"]:
            result["warnings"].append("SHA-256 mismatch")

        reader = PdfReader(str(path), strict=False)

        if reader.is_encrypted:
            result["warnings"].append("PDF is encrypted")
            result["status"] = "WARNING"
            return result

        result["page_count"] = len(reader.pages)

        for page in reader.pages:
            text = page.extract_text() or ""
            result["text_characters"] += len(text.strip())

            if len(text.strip()) > 50:
                result["pages_with_text"] += 1

        if result["page_count"] == 0:
            result["warnings"].append("PDF contains no pages")

        if result["text_characters"] < 1000:
            result["warnings"].append("Very little extractable text; inspect for OCR requirements")

        if not result["sha256_valid"]:
            result["status"] = "FAIL"
        elif result["warnings"]:
            result["status"] = "WARNING"

    except Exception as error:
        result["status"] = "FAIL"
        result["warnings"].append(str(error))

    return result


def main():
    records = load_metadata()
    results = []
    ids = [record.get("arxiv_id") for record in records]

    duplicates = [
        paper_id
        for paper_id, count in Counter(ids).items()
        if count > 1
    ]

    for record in records:
        result = audit_document(record)
        results.append(result)

        print(
            f"{result['status']} | "
            f"{result['arxiv_id']} | "
            f"Pages: {result['page_count']} | "
            f"Characters: {result['text_characters']}"
        )

        for warning in result["warnings"]:
            print(f"  Warning: {warning}")

    with REPORT_FILE.open("w", encoding="utf-8") as file:
        for result in results:
            file.write(json.dumps(result, ensure_ascii=False) + "\n")

    passed = sum(result["status"] == "PASS" for result in results)
    warnings = sum(result["status"] == "WARNING" for result in results)
    failed = sum(result["status"] == "FAIL" for result in results)

    print("\nDataset audit summary")
    print(f"Metadata records: {len(records)}")
    print(f"Passed: {passed}")
    print(f"Warnings: {warnings}")
    print(f"Failed: {failed}")
    print(f"Duplicate IDs: {len(duplicates)}")
    print(f"Audit report: {REPORT_FILE}")

    if duplicates:
        print(f"Duplicate IDs: {duplicates}")


if __name__ == "__main__":
    main()
