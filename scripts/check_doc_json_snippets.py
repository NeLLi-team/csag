#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATHS = [ROOT / name for name in ("README.md", "docs", "examples", "tests", "skills")]
SCHEMA = json.loads((ROOT / "skills/csag-extraction/assets/csag.schema.json").read_text(encoding="utf-8"))


def enum_values(name: str) -> set[str]:
    return set(SCHEMA["$defs"][name]["enum"])


CONTEXT_FACETS = enum_values("ContextFacet")
POLARITIES = enum_values("Polarity")
CLAIM_ROLES = enum_values("ClaimRole")
NORMALIZATION_STATUSES = enum_values("NormalizationStatus")
RESEARCH_STATES = enum_values("ResearchState")
NEXT_ACTION_TYPES = enum_values("NextActionType")
EXECUTION_STATUSES = enum_values("ExecutionStatus")
ASSERTION_RELATION_TYPES = enum_values("AssertionRelationType")
STALE_ALIASES = {"facet": "context_facet", "affected_assertions": "impacted_assertions"}
SNIPPET_CLASSES = (
    "Context",
    "Assertion",
    "EvidenceLink",
    "EvidenceItem",
    "StudyCritique",
    "KnowledgeGap",
    "AssertionRelation",
    "ResearchStateRecord",
    "NextAction",
    "Execution",
)
ALLOWED_FIELDS = {
    class_name: set(SCHEMA["$defs"][class_name]["properties"])
    for class_name in SNIPPET_CLASSES
}
CLASS_VALIDATORS = {
    class_name: Draft202012Validator(
        {
            "$schema": SCHEMA.get("$schema"),
            "$defs": SCHEMA["$defs"],
            "$ref": f"#/$defs/{class_name}",
        }
    )
    for class_name in SNIPPET_CLASSES
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate JSON snippets in Markdown docs against common CSAG fields/enums.")
    parser.add_argument("paths", nargs="*", type=Path, default=DEFAULT_PATHS)
    parser.add_argument("--report-out", type=Path)
    return parser.parse_args()


def markdown_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        path = path.expanduser()
        if not path.is_absolute():
            path = ROOT / path
        if path.is_file() and path.suffix.lower() == ".md":
            files.append(path)
        elif path.is_dir():
            files.extend(p for p in path.rglob("*.md") if ".git" not in p.parts)
    return sorted(set(files))


def infer_class(obj: dict) -> str | None:
    keys = set(obj)
    if "assertion_text" in keys:
        return "Assertion"
    if "context_facet" in keys or "facet" in keys:
        return "Context"
    if {"evidence_item", "assertion"} <= keys:
        return "EvidenceLink"
    if "evidence_type" in keys or "evidence_text" in keys:
        return "EvidenceItem"
    if "critique_type" in keys:
        return "StudyCritique"
    if "gap_type" in keys:
        return "KnowledgeGap"
    if {"from_assertion", "to_assertion"} <= keys:
        return "AssertionRelation"
    if "state" in keys and ("current_read" in keys or "recommended_next_actions" in keys):
        return "ResearchStateRecord"
    if "action_type" in keys:
        return "NextAction"
    if "execution_type" in keys or "execution_status" in keys:
        return "Execution"
    return None


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def add_issue(issues: list[dict], path: Path, line: int, klass: str, field: str, reason: str, suggested_fix: str, value: object = None) -> None:
    issues.append({"file": display_path(path), "line": line, "class": klass, "field": field, "value": value, "reason": reason, "suggested_fix": suggested_fix})


def validate_object(obj: object, path: Path, line: int, issues: list[dict]) -> None:
    if isinstance(obj, list):
        for item in obj:
            validate_object(item, path, line, issues)
        return
    if not isinstance(obj, dict):
        return
    klass = infer_class(obj)
    if not klass:
        return
    schema_candidate = dict(obj)
    schema_candidate.setdefault("id", f"csag:snippet/{klass}/S0001")
    for error in sorted(
        CLASS_VALIDATORS[klass].iter_errors(schema_candidate),
        key=lambda item: list(item.absolute_path),
    ):
        field = ".".join(str(part) for part in error.absolute_path) or "(object)"
        add_issue(
            issues,
            path,
            line,
            klass,
            field,
            f"JSON Schema violation: {error.message}",
            "Make the example conform to the generated class schema, or mark an intentional counterexample with csag-snippet-ignore.",
            obj.get(field) if field in obj else None,
        )
    for field, replacement in STALE_ALIASES.items():
        if field in obj:
            add_issue(issues, path, line, klass, field, "stale CSAG field alias", f"Use {replacement}.", obj.get(field))
    allowed = ALLOWED_FIELDS.get(klass, set())
    for field in obj:
        if field not in allowed and field not in STALE_ALIASES:
            add_issue(issues, path, line, klass, field, "unknown field for inferred CSAG class", "Use the current CSAG schema field name or add an explicit opt-out comment.", obj.get(field))
    if klass == "Context" and "context_facet" in obj and obj["context_facet"] not in CONTEXT_FACETS:
        add_issue(issues, path, line, klass, "context_facet", "invalid ContextFacet enum value", "Use one of: " + ", ".join(sorted(CONTEXT_FACETS)) + ".", obj["context_facet"])
    if klass == "EvidenceLink" and "polarity" in obj and obj["polarity"] not in POLARITIES:
        add_issue(issues, path, line, klass, "polarity", "invalid EvidenceLink polarity", "Use supports, refutes, mixed, or inconclusive.", obj["polarity"])
    if klass == "Assertion":
        if "claim_role" in obj and obj["claim_role"] not in CLAIM_ROLES:
            add_issue(issues, path, line, klass, "claim_role", "invalid claim_role enum value", "Use a current ClaimRole value.", obj["claim_role"])
        if "normalization_status" in obj and obj["normalization_status"] not in NORMALIZATION_STATUSES:
            add_issue(issues, path, line, klass, "normalization_status", "invalid normalization_status enum value", "Use raw, partially_normalized, or fully_normalized.", obj["normalization_status"])
    if klass == "AssertionRelation" and "relation_type" in obj and obj["relation_type"] not in ASSERTION_RELATION_TYPES:
        add_issue(issues, path, line, klass, "relation_type", "invalid AssertionRelationType enum value", "Use a current AssertionRelationType value.", obj["relation_type"])
    if klass == "ResearchStateRecord" and "state" in obj and obj["state"] not in RESEARCH_STATES:
        add_issue(issues, path, line, klass, "state", "invalid ResearchState enum value", "Use a current ResearchState value.", obj["state"])
    if klass == "NextAction" and "action_type" in obj and obj["action_type"] not in NEXT_ACTION_TYPES:
        add_issue(issues, path, line, klass, "action_type", "invalid NextActionType enum value", "Use a current NextActionType value.", obj["action_type"])
    if klass == "Execution" and "execution_status" in obj and obj["execution_status"] not in EXECUTION_STATUSES:
        add_issue(issues, path, line, klass, "execution_status", "invalid ExecutionStatus enum value", "Use a current ExecutionStatus value.", obj["execution_status"])


def main() -> int:
    args = parse_args()
    issues: list[dict] = []
    fence_re = re.compile(r"(^|\n)(?P<fence>```json\s*\n(?P<body>.*?)\n```)", re.DOTALL | re.IGNORECASE)
    for path in markdown_files(args.paths):
        text = path.read_text(encoding="utf-8")
        for match in fence_re.finditer(text):
            prefix = text[:match.start("fence")]
            line = prefix.count("\n") + 1
            if "csag-snippet-ignore" in prefix[-200:] or "csag-snippet-ignore" in match.group("body"):
                continue
            try:
                payload = json.loads(match.group("body"))
            except json.JSONDecodeError as exc:
                add_issue(issues, path, line, "JSON", "(parse)", f"invalid JSON snippet: {exc.msg}", "Fix the JSON syntax or mark intentional pseudocode with csag-snippet-ignore.")
                continue
            validate_object(payload, path, line, issues)
    report = {"ok": not issues, "issues": issues, "checked_files": [display_path(p) for p in markdown_files(args.paths)]}
    if args.report_out:
        args.report_out.expanduser().resolve().write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
