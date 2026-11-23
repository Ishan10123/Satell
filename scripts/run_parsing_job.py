import json
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rag_pipeline.ingestion.approval import load_approval_registry
from rag_pipeline.ingestion.approval_workflow import load_approval_paths
from rag_pipeline.ingestion.discovery import read_jsonl
from rag_pipeline.ingestion.parsing_job import run_parsing_job
from rag_pipeline.ingestion.registry import load_config
from rag_pipeline.parsing import load_parser_registry


METADATA_DIR = PROJECT_ROOT / "knowledge_base" / "metadata"
APPROVAL_PATHS = load_approval_paths(PROJECT_ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse approved documents or an explicitly operator-authorized unreviewed run.")
    parser.add_argument("--operator-authorized-unreviewed", action="store_true",
                        help="use operator instruction for this run without changing license decision registries")
    args = parser.parse_args()
    config = load_config(PROJECT_ROOT / "configs" / "ingestion_sources.json")
    registry = load_approval_registry(APPROVAL_PATHS["source_registry"])
    document_registry_path = APPROVAL_PATHS["document_registry"]
    document_registry = json.loads(document_registry_path.read_text(encoding="utf-8-sig")) if document_registry_path.is_file() else {}
    summary = run_parsing_job(
        documents=read_jsonl(METADATA_DIR / "ingestion_inventory.jsonl"),
        approval_registry=registry,
        project_root=PROJECT_ROOT,
        output_root=PROJECT_ROOT / "knowledge_base" / "processed" / "parse_runs",
        allowed_extensions=config.allowed_extensions,
        approved_license_statuses=config.approved_license_statuses,
        document_approval_registry=document_registry,
        operator_authorized_unreviewed=args.operator_authorized_unreviewed,
        parser_registry=load_parser_registry(config.parser_registry_path) if config.parser_registry_path else None,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
