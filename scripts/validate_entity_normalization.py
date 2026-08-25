#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "supplementary" / "entity-normalization"

ENTITY_COLUMNS = [
    "csag_entity_id",
    "label",
    "entity_category",
    "biolink_class",
    "canonical_curie",
    "canonical_uri",
    "xrefs",
    "aliases",
    "match_type",
    "confidence",
    "curation_status",
    "source_document",
]

MENTION_COLUMNS = [
    "mention_id",
    "csag_entity_id",
    "document_id",
    "section_type",
    "start_char",
    "end_char",
    "exact_text",
    "mention_type",
    "confidence",
    "extractor",
    "needs_review",
]

CURIE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*:[A-Za-z0-9][A-Za-z0-9_.:/%+-]*$")
VALID_CURATION = {"unreviewed", "needs_review", "human_verified", "human_corrected", "rejected"}


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def is_uri(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def is_curie_or_uri(value: str) -> bool:
    return bool(CURIE_RE.match(value) or is_uri(value))


def split_multi(value: str) -> list[str]:
    return [item.strip() for item in value.split("|") if item.strip()]


def load_profile(path: Path, errors: list[str]) -> dict:
    if not path.exists():
        errors.append(f"missing profile: {path}")
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        errors.append(f"invalid YAML in {path}: {exc}")
        return {}
    if not isinstance(loaded, dict):
        errors.append(f"profile must be a mapping: {path}")
        return {}
    return loaded


def check_columns(path: Path, rows: list[dict[str, str]], required: list[str], errors: list[str]) -> None:
    if not rows:
        errors.append(f"{path.name} has no data rows")
        return
    observed = list(rows[0].keys())
    missing = [column for column in required if column not in observed]
    if missing:
        errors.append(f"{path.name} missing columns: {missing}")


def validate_catalog(rows: list[dict[str, str]], profile: dict, errors: list[str]) -> set[str]:
    mappings = profile.get("category_mappings")
    allowed_categories = set(mappings) if isinstance(mappings, dict) else set()
    allowed_namespaces = set(profile.get("allowed_namespaces") or [])
    entity_ids: set[str] = set()

    for index, row in enumerate(rows, start=2):
        row_label = f"entity_catalog.tsv:{index}"
        entity_id = row.get("csag_entity_id", "").strip()
        if not entity_id:
            errors.append(f"{row_label}: csag_entity_id is required")
        elif entity_id in entity_ids:
            errors.append(f"{row_label}: duplicate csag_entity_id {entity_id}")
        entity_ids.add(entity_id)

        for field in ("label", "entity_category", "biolink_class", "canonical_curie", "confidence", "curation_status", "source_document"):
            if not row.get(field, "").strip():
                errors.append(f"{row_label}: {field} is required")

        category = row.get("entity_category", "").strip()
        if allowed_categories and category not in allowed_categories:
            errors.append(f"{row_label}: entity_category {category!r} is not declared in entity_profile.yaml")

        mapping = mappings.get(category, {}) if isinstance(mappings, dict) else {}
        expected_class = mapping.get("biolink_class") if isinstance(mapping, dict) else None
        if expected_class and row.get("biolink_class", "").strip() != expected_class:
            errors.append(f"{row_label}: biolink_class should be {expected_class} for category {category}")

        curie = row.get("canonical_curie", "").strip()
        if curie and not is_curie_or_uri(curie):
            errors.append(f"{row_label}: canonical_curie is not a CURIE/URI: {curie}")
        if curie and ":" in curie and allowed_namespaces:
            prefix = curie.split(":", 1)[0]
            if prefix not in allowed_namespaces:
                errors.append(f"{row_label}: canonical_curie prefix {prefix!r} is not allowed by the profile")

        uri = row.get("canonical_uri", "").strip()
        if uri and not is_uri(uri):
            errors.append(f"{row_label}: canonical_uri must be http(s): {uri}")

        for xref in split_multi(row.get("xrefs", "")):
            if not is_curie_or_uri(xref):
                errors.append(f"{row_label}: xref is not a CURIE/URI: {xref}")

        try:
            confidence = float(row.get("confidence", ""))
        except ValueError:
            errors.append(f"{row_label}: confidence must be numeric")
        else:
            if confidence < 0 or confidence > 1:
                errors.append(f"{row_label}: confidence must be between 0 and 1")

        curation_status = row.get("curation_status", "").strip()
        if curation_status and curation_status not in VALID_CURATION:
            errors.append(f"{row_label}: unsupported curation_status {curation_status!r}")

    return entity_ids


def validate_mentions(rows: list[dict[str, str]], entity_ids: set[str], errors: list[str]) -> set[str]:
    mentioned_entities: set[str] = set()
    mention_ids: set[str] = set()
    for index, row in enumerate(rows, start=2):
        row_label = f"entity_mentions.tsv:{index}"
        mention_id = row.get("mention_id", "").strip()
        if not mention_id:
            errors.append(f"{row_label}: mention_id is required")
        elif mention_id in mention_ids:
            errors.append(f"{row_label}: duplicate mention_id {mention_id}")
        mention_ids.add(mention_id)

        entity_id = row.get("csag_entity_id", "").strip()
        if entity_id not in entity_ids:
            errors.append(f"{row_label}: csag_entity_id does not resolve to catalog entity: {entity_id}")
        mentioned_entities.add(entity_id)

        for field in ("document_id", "section_type", "exact_text", "mention_type", "extractor", "needs_review"):
            if not row.get(field, "").strip():
                errors.append(f"{row_label}: {field} is required")

        try:
            start = int(row.get("start_char", ""))
            end = int(row.get("end_char", ""))
        except ValueError:
            errors.append(f"{row_label}: start_char and end_char must be integers")
        else:
            if start < 0 or end <= start:
                errors.append(f"{row_label}: invalid character offsets {start}-{end}")

        try:
            confidence = float(row.get("confidence", ""))
        except ValueError:
            errors.append(f"{row_label}: confidence must be numeric")
        else:
            if confidence < 0 or confidence > 1:
                errors.append(f"{row_label}: confidence must be between 0 and 1")

        if row.get("needs_review", "").strip().lower() not in {"true", "false"}:
            errors.append(f"{row_label}: needs_review must be true or false")
    return mentioned_entities


def validate_report(path: Path, entity_rows: list[dict[str, str]], mention_rows: list[dict[str, str]], errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing report: {path}")
        return
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path}: {exc}")
        return
    required = ("source_document", "entity_count", "mention_count", "namespace_coverage", "unmapped_entities", "ambiguous_mappings", "ontology_versions", "curator_review_status")
    for key in required:
        if key not in report:
            errors.append(f"normalization_report.json missing key: {key}")
    if report.get("entity_count") != len(entity_rows):
        errors.append("normalization_report.json entity_count does not match entity_catalog.tsv")
    if report.get("mention_count") != len(mention_rows):
        errors.append("normalization_report.json mention_count does not match entity_mentions.tsv")


def validate_bundle(path: Path, entity_rows: list[dict[str, str]], mention_rows: list[dict[str, str]], errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing JSON bundle: {path}")
        return
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path}: {exc}")
        return
    if len(bundle.get("entities", []) or []) != len(entity_rows):
        errors.append("example_entity_bundle.json entities count does not match entity_catalog.tsv")
    if len(bundle.get("mentions", []) or []) != len(mention_rows):
        errors.append("example_entity_bundle.json mentions count does not match entity_mentions.tsv")


def validate_supplement(supplement_dir: Path) -> dict:
    errors: list[str] = []
    profile = load_profile(supplement_dir / "entity_profile.yaml", errors)

    catalog_path = supplement_dir / "entity_catalog.tsv"
    mentions_path = supplement_dir / "entity_mentions.tsv"
    mappings_path = supplement_dir / "ontology_mappings.tsv"

    if not catalog_path.exists():
        errors.append(f"missing catalog: {catalog_path}")
        catalog_rows: list[dict[str, str]] = []
    else:
        catalog_rows = read_tsv(catalog_path)
        check_columns(catalog_path, catalog_rows, ENTITY_COLUMNS, errors)

    if not mentions_path.exists():
        errors.append(f"missing mentions: {mentions_path}")
        mention_rows: list[dict[str, str]] = []
    else:
        mention_rows = read_tsv(mentions_path)
        check_columns(mentions_path, mention_rows, MENTION_COLUMNS, errors)

    if not mappings_path.exists():
        errors.append(f"missing mappings: {mappings_path}")
        mapping_rows: list[dict[str, str]] = []
    else:
        mapping_rows = read_tsv(mappings_path)
        check_columns(
            mappings_path,
            mapping_rows,
            ["entity_category", "biolink_class", "preferred_namespaces", "fallback_namespaces", "notes"],
            errors,
        )

    entity_ids = validate_catalog(catalog_rows, profile, errors)
    mentioned_entities = validate_mentions(mention_rows, entity_ids, errors)
    unmentioned = sorted(entity_ids - mentioned_entities)
    if unmentioned:
        errors.append(f"catalog entities lack mention rows: {unmentioned}")

    validate_report(supplement_dir / "normalization_report.json", catalog_rows, mention_rows, errors)
    validate_bundle(supplement_dir / "example_entity_bundle.json", catalog_rows, mention_rows, errors)

    return {
        "ok": not errors,
        "supplement_dir": str(supplement_dir),
        "entity_count": len(catalog_rows),
        "mention_count": len(mention_rows),
        "mapping_count": len(mapping_rows),
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a CSAG entity-normalization supplement.")
    parser.add_argument("--supplement-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--report-out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = validate_supplement(args.supplement_dir.expanduser().resolve())
    if args.report_out:
        args.report_out.expanduser().resolve().write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
