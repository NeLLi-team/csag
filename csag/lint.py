from __future__ import annotations

import json
from pathlib import Path

from .export import load_extraction
from .paths import CommandResult
from .provenance import input_records


def lint_extraction(extraction_json: Path, *, report_out: Path | None = None, strict: bool = False) -> CommandResult:
    extraction_path = extraction_json.expanduser().resolve()
    extraction = load_extraction(extraction_path)
    root_id = extraction.get("id", "")
    compact_root_id = root_id.replace(":", "").replace("/", "_")
    issues: list[dict[str, str]] = []

    def add(object_id: str, field: str, reason: str, fix: str) -> None:
        issues.append({"object_id": object_id, "field": field, "reason": reason, "suggested_fix": fix})

    seen: set[str] = set()
    for collection in (
        "artifacts",
        "datasets",
        "entities",
        "studies",
        "experiments",
        "assertions",
        "evidence_items",
        "evidence_links",
        "inferences",
        "assertion_relations",
        "critiques",
        "knowledge_gaps",
        "qa_items",
    ):
        for item in extraction.get(collection, []) or []:
            item_id = item.get("id", "")
            if not item_id:
                add(collection, "id", "Missing object ID.", "Assign a deterministic local ID.")
                continue
            if item_id in seen:
                add(item_id, "id", "Duplicate object ID.", "Rename one of the duplicate objects.")
            seen.add(item_id)
            if root_id and root_id not in item_id and compact_root_id not in item_id and item_id.startswith("csag:"):
                add(item_id, "id", "ID does not include the document namespace.", "Use the document ID in local CSAG object IDs.")
            spans = item.get("text_spans", [])
            if collection in {"assertions", "evidence_items", "critiques", "knowledge_gaps"} and not spans:
                add(item_id, "text_spans", "Central object is not grounded to source text.", "Add at least one TextSpan.")
            for span in spans or []:
                if root_id and span.get("document_id") != root_id:
                    add(item_id, "text_spans[].document_id", "Span document_id differs from PaperExtraction.id.", "Use the same document ID as the root extraction.")

    for assertion in extraction.get("assertions", []) or []:
        assertion_id = assertion.get("id", "")
        if assertion.get("criticality") in {"core", "major"} and not assertion.get("falsification_criteria"):
            add(assertion_id, "falsification_criteria", "Core or major assertion lacks falsification criteria.", "Add concrete falsification criteria.")

    resolved_out = report_out.expanduser().resolve() if report_out else None
    report = {
        "ok": not issues,
        "strict": bool(strict),
        "inputs": input_records(
            base_dir=resolved_out.parent if resolved_out else extraction_path.parent,
            extraction=extraction_path,
        ),
        "issues": issues,
    }
    if resolved_out:
        resolved_out.parent.mkdir(parents=True, exist_ok=True)
        resolved_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(report, indent=2))
    code = 1 if strict and issues else 0
    return CommandResult(code == 0, code, resolved_out, report if resolved_out else None)
