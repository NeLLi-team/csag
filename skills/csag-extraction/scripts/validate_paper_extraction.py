#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from csag_provenance import input_record, input_records


ASSETS = Path(__file__).resolve().parents[1] / "assets"
JSON_SCHEMA_PATH = ASSETS / "csag.schema.json"
JSON_SCHEMA = json.loads(JSON_SCHEMA_PATH.read_text(encoding="utf-8"))


def enum_values(name: str) -> set[str]:
    return set(JSON_SCHEMA["$defs"][name]["enum"])


DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
PMID_RE = re.compile(r"\bPMID[:\s]+(\d{6,9})\b", re.IGNORECASE)
DATASET_SIGNAL_RE = re.compile(
    r"\b(data availability|accession|project id|repository|zenodo|img/m|data portal|sra|geo|pride|available at|downloaded at)\b",
    re.IGNORECASE,
)
FIGURE_SIGNAL_RE = re.compile(
    r"^\s*(fig(?:ure)?\.?|table|supplementary figure|supplementary table)\b",
    re.IGNORECASE,
)

ASSERTION_CRITICALITIES = enum_values("AssertionCriticality")
CLAIM_ROLES = enum_values("ClaimRole")
NORMALIZATION_STATUSES = enum_values("NormalizationStatus")
DECISIVE_POLARITIES = {"supports", "refutes", "mixed"}
POLARITIES = enum_values("Polarity")
STRENGTH_LEVELS = enum_values("StrengthLevel")
ADEQUATE_STRENGTH_LEVELS = {"very_strong", "strong", "moderate"}
PROMOTED_CURATION_STATUSES = {"human_verified", "human_corrected"}
ARTIFACT_TYPES = enum_values("ArtifactType")
CONTEXT_FACETS = enum_values("ContextFacet")
ASSERTION_RELATION_TYPES = enum_values("AssertionRelationType")
RESEARCH_STATES = enum_values("ResearchState")
NEXT_ACTION_TYPES = enum_values("NextActionType")
EXECUTION_STATUSES = enum_values("ExecutionStatus")
VALIDATOR_VERSION = "1.0.0"
PROFILE_ALIASES = {
    "candidate": "paper_local",
    "ground_truth": "benchmark_key",
    "core": "paper_local",
    "benchmark": "benchmark_key",
}
STRICTNESS_PROFILES = {"lite", "paper_local", "promoted_claim", "benchmark_key"}
MODULE_PROFILES = {"core", "bio", "reasoning", "research_state", "benchmark"}
MODULE_ORDER = ("core", "bio", "reasoning", "research_state", "benchmark")
PROFILE_CHOICES = (
    "lite",
    "paper_local",
    "promoted_claim",
    "benchmark_key",
    "candidate",
    "ground_truth",
    "core",
    "bio",
    "reasoning",
    "research_state",
    "benchmark",
)
ID_LIST_KEYS = (
    "artifacts",
    "datasets",
    "entities",
    "studies",
    "assertions",
    "evidence_items",
    "evidence_links",
    "inferences",
    "assertion_relations",
    "critiques",
    "knowledge_gaps",
    "qa_items",
    "research_states",
    "next_actions",
    "executions",
    "extraction_activities",
)
ID_PATTERNS = {
    "artifacts": ("artifact", "F"),
    "datasets": ("dataset", "D"),
    "entities": ("entity", "N"),
    "studies": ("study", "S"),
    "assertions": ("assertion", "A"),
    "evidence_items": ("evidence", "E"),
    "evidence_links": ("elink", "L"),
    "inferences": ("inference", "I"),
    "assertion_relations": ("relation", "AR"),
    "critiques": ("critique", "R"),
    "knowledge_gaps": ("gap", "G"),
    "qa_items": ("qa", "Q"),
    "research_states": ("state", "RS"),
    "next_actions": ("action", "NA"),
    "executions": ("execution", "EX"),
    "extraction_activities": ("activity", "ACT"),
}
CRITICALITY_REPAIRS = {
    "high": "core",
    "medium": "major",
    "moderate": "major",
    "low": "supporting",
    "minor": "supporting",
    "none": "background",
}
FIELD_ALIASES = {
    "evidence_links": {
        "evidence_id": "evidence_item",
        "evidenceItem": "evidence_item",
        "evidenceItemId": "evidence_item",
        "assertion_id": "assertion",
        "assertionId": "assertion",
    },
    "inferences": {
        "output_assertion_id": "output_assertion",
        "outputAssertion": "output_assertion",
        "outputAssertionId": "output_assertion",
    },
    "assertion_relations": {
        "source_assertion": "from_assertion",
        "source_assertion_id": "from_assertion",
        "from_assertion_id": "from_assertion",
        "target_assertion": "to_assertion",
        "target_assertion_id": "to_assertion",
        "to_assertion_id": "to_assertion",
    },
    "datasets": {
        "url": "dataset_url",
        "data_url": "dataset_url",
        "project_id": "accession",
        "accession_id": "accession",
        "database": "repository",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a CSAG PaperExtraction with repo-specific enforcement rules."
    )
    parser.add_argument("extraction_json", type=Path)
    parser.add_argument("--source-markdown", type=Path, default=None)
    parser.add_argument("--article-json", type=Path, default=None)
    parser.add_argument("--report-out", type=Path, required=True)
    parser.add_argument(
        "--profile",
        default="paper_local",
        help=(
            "Validation profile. Existing strictness profiles: lite, paper_local, "
            "promoted_claim, benchmark_key. Module profiles may be used alone or "
            "comma-combined: core, bio, reasoning, research_state, benchmark "
            "(for example core,bio or core,research_state). candidate and "
            "ground_truth are legacy aliases."
        ),
    )
    parser.add_argument(
        "--repair-out",
        type=Path,
        default=None,
        help=(
            "Write a mechanically repaired extraction before validation. Repairs are "
            "limited to deterministic schema-shape fixes such as field aliases, enum "
            "aliases, scalar-to-list coercions, missing deterministic IDs, and inferred "
            "artifact types."
        ),
    )
    return parser.parse_args()


def ordered_modules(modules: set[str]) -> list[str]:
    return [module for module in MODULE_ORDER if module in modules]


def parse_profile(value: str) -> tuple[str, str, set[str], list[str]]:
    """Return (reported_profile, strictness_profile, module_profiles, errors)."""
    raw_tokens = [token.strip() for token in str(value or "paper_local").split(",") if token.strip()]
    if not raw_tokens:
        raw_tokens = ["paper_local"]

    strictness = "paper_local"
    modules: set[str] = set()
    errors: list[str] = []
    reported_tokens: list[str] = []

    for token in raw_tokens:
        canonical = PROFILE_ALIASES.get(token, token)
        reported_tokens.append(canonical)
        if canonical in STRICTNESS_PROFILES:
            if canonical == "lite":
                strictness = "lite"
            elif canonical == "promoted_claim" and strictness in {"paper_local", "lite"}:
                strictness = "promoted_claim"
            elif canonical == "benchmark_key":
                strictness = "benchmark_key"
            modules.add("core")
            if canonical == "benchmark_key":
                modules.add("benchmark")
        elif canonical in MODULE_PROFILES:
            modules.add(canonical)
            if canonical == "benchmark":
                strictness = "benchmark_key"
        else:
            allowed = sorted(set(PROFILE_CHOICES) | STRICTNESS_PROFILES | MODULE_PROFILES)
            errors.append(
                issue(
                    "(input)",
                    "--profile",
                    f"unknown validation profile '{token}'",
                    "Use one of: " + ", ".join(allowed) + "; module profiles may be comma-combined.",
                )
            )

    if not modules:
        modules.add("core")
    if "benchmark" in modules:
        strictness = "benchmark_key"
    if strictness in {"promoted_claim", "benchmark_key"}:
        modules.add("core")
    reported_profile = ",".join(ordered_modules(modules)) if set(raw_tokens) & MODULE_PROFILES else strictness
    return reported_profile, strictness, modules, errors


def load_json(path: Path | None) -> dict | None:
    if path is None:
        return None
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def front_matter_only(markdown: str) -> str:
    if not markdown:
        return ""
    for marker in ("\n# 1 ", "\n# Introduction", "\n## Introduction"):
        idx = markdown.find(marker)
        if idx != -1:
            return markdown[:idx]
    return markdown[:4000]


def collect_parameter_map(extraction: dict) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for activity in extraction.get("extraction_activities", []):
        for item in activity.get("parameters", []):
            key = item.get("key")
            value = item.get("value")
            if isinstance(key, str) and isinstance(value, str):
                mapping[key] = value
    return mapping


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def issue(object_id: object, field_path: str, reason: str, suggested_fix: str) -> str:
    object_label = object_id if isinstance(object_id, str) and object_id else "(unknown id)"
    return (
        f"object={object_label}; field={field_path}; reason={reason}; "
        f"suggested_fix={suggested_fix}"
    )


def issue_code(reason: str) -> str:
    code = re.sub(r"[^a-z0-9]+", "_", reason.lower()).strip("_")
    return code[:80] or "validation_error"


def structured_issue(message: str) -> dict[str, str]:
    match = re.match(
        r"^object=(?P<object_id>.*?); field=(?P<field_path>.*?); reason=(?P<reason>.*?); suggested_fix=(?P<suggested_fix>.*)$",
        message,
    )
    if not match:
        return {
            "code": issue_code(message),
            "object_id": "",
            "field_path": "",
            "reason": message,
            "suggested_fix": "",
        }
    payload = {key: value.strip() for key, value in match.groupdict().items()}
    payload["code"] = issue_code(payload["reason"])
    return payload


def error_summary(errors: list[str]) -> dict[str, int]:
    counter = Counter(item["code"] for item in (structured_issue(error) for error in errors))
    return dict(sorted(counter.items()))


def repair_doc_id(extraction: dict) -> str:
    doc_id = extraction.get("id")
    if isinstance(doc_id, str) and doc_id:
        return doc_id
    doi = extraction.get("doi")
    if isinstance(doi, str) and doi:
        return f"doi:{doi}"
    pmid = extraction.get("pmid")
    if isinstance(pmid, str) and pmid:
        return f"pmid:{pmid}"
    return "csag:doc/unknown"


def repair_action(actions: list[dict[str, Any]], code: str, path: str, before: Any, after: Any) -> None:
    actions.append({"code": code, "path": path, "before": before, "after": after})


def infer_artifact_type(artifact: dict) -> str:
    text = " ".join(
        str(artifact.get(field) or "")
        for field in ("artifact_type", "artifact_label", "label", "caption", "description")
    ).lower()
    if "table" in text:
        return "table"
    if "supplement" in text:
        return "supplementary"
    if "equation" in text:
        return "equation"
    if "protocol" in text:
        return "protocol"
    if "code" in text or "software" in text:
        return "code"
    if "fig" in text:
        return "figure"
    return "other"


def repair_paper_extraction(extraction: dict) -> tuple[dict, list[dict[str, Any]]]:
    repaired = deepcopy(extraction)
    actions: list[dict[str, Any]] = []
    doc_id = repair_doc_id(repaired)

    for collection, (namespace, prefix) in ID_PATTERNS.items():
        items = repaired.get(collection)
        if not isinstance(items, list):
            continue
        seen = {item.get("id") for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)}
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict) or item.get("id"):
                continue
            candidate_index = index
            while True:
                candidate = f"csag:{namespace}/{doc_id}/{prefix}{candidate_index:04d}"
                if candidate not in seen:
                    break
                candidate_index += 1
            item["id"] = candidate
            seen.add(candidate)
            repair_action(actions, "assign_missing_id", f"{collection}[{index - 1}].id", "", candidate)

    for collection, aliases in FIELD_ALIASES.items():
        items = repaired.get(collection)
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            for alias, canonical in aliases.items():
                if not item.get(canonical) and item.get(alias):
                    item[canonical] = item[alias]
                    repair_action(actions, "copy_field_alias", f"{collection}[{index}].{canonical}", alias, canonical)

    for index, assertion in enumerate(repaired.get("assertions", []) or []):
        if not isinstance(assertion, dict):
            continue
        criticality = assertion.get("criticality")
        if isinstance(criticality, str):
            normalized = CRITICALITY_REPAIRS.get(criticality.strip().lower())
            if normalized:
                assertion["criticality"] = normalized
                repair_action(actions, "normalize_criticality", f"assertions[{index}].criticality", criticality, normalized)
        criteria = assertion.get("falsification_criteria")
        if isinstance(criteria, str) and criteria.strip():
            assertion["falsification_criteria"] = [criteria.strip()]
            repair_action(
                actions,
                "coerce_falsification_criteria_list",
                f"assertions[{index}].falsification_criteria",
                criteria,
                assertion["falsification_criteria"],
            )
        contexts = assertion.get("contexts")
        if isinstance(contexts, dict):
            assertion["contexts"] = [contexts]
            repair_action(actions, "coerce_contexts_list", f"assertions[{index}].contexts", "object", "list")

    for index, artifact in enumerate(repaired.get("artifacts", []) or []):
        if not isinstance(artifact, dict):
            continue
        artifact_type = artifact.get("artifact_type")
        if not isinstance(artifact_type, str) or artifact_type not in ARTIFACT_TYPES:
            inferred = infer_artifact_type(artifact)
            artifact["artifact_type"] = inferred
            repair_action(actions, "infer_artifact_type", f"artifacts[{index}].artifact_type", artifact_type, inferred)

    for index, activity in enumerate(repaired.get("extraction_activities", []) or []):
        if not isinstance(activity, dict):
            continue
        parameters = activity.get("parameters")
        if isinstance(parameters, dict):
            converted = [{"key": str(key), "value": str(value)} for key, value in parameters.items()]
            activity["parameters"] = converted
            repair_action(actions, "coerce_parameters_list", f"extraction_activities[{index}].parameters", "object", "list")

    return repaired, actions


def nonempty_string_list(value: object) -> bool:
    return isinstance(value, list) and any(isinstance(item, str) and item.strip() for item in value)


def has_text_spans(item: dict | None) -> bool:
    return bool(isinstance(item, dict) and isinstance(item.get("text_spans"), list) and item.get("text_spans"))


def collect_ids(extraction: dict, errors: list[str]) -> dict[str, set[str]]:
    global_locations: dict[str, list[str]] = {}

    def walk(value: object, path: str) -> None:
        if isinstance(value, dict):
            item_id = value.get("id")
            if isinstance(item_id, str) and item_id:
                global_locations.setdefault(item_id, []).append(path)
            for key, nested in value.items():
                walk(nested, f"{path}.{key}")
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                walk(nested, f"{path}[{index}]")

    walk(extraction, "paper_extraction")
    duplicates = {item_id: paths for item_id, paths in global_locations.items() if len(paths) > 1}
    for item_id, paths in sorted(duplicates.items()):
        errors.append(
            issue(
                item_id,
                "id",
                f"ID is reused at {', '.join(paths)}",
                "Assign one globally unique ID to each object occurrence within the PaperExtraction.",
            )
        )

    ids_by_key: dict[str, set[str]] = {}
    for key in ID_LIST_KEYS:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for item in extraction.get(key, []) or []:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            if not isinstance(item_id, str) or not item_id:
                continue
            if item_id in seen:
                duplicates.add(item_id)
            seen.add(item_id)
        if duplicates:
            errors.append(
                issue(
                    ",".join(sorted(duplicates)),
                    key,
                    "duplicate IDs are present",
                    "Rename duplicate objects so every ID is unique within the PaperExtraction.",
                )
            )
        ids_by_key[key] = seen
    experiment_ids: set[str] = set()
    for study in extraction.get("studies", []) or []:
        if not isinstance(study, dict):
            continue
        for experiment in study.get("experiments", []) or []:
            if isinstance(experiment, dict) and isinstance(experiment.get("id"), str):
                experiment_ids.add(experiment["id"])
    ids_by_key["experiments"] = experiment_ids
    return ids_by_key


def expect_required_ref(ref: object, known_ids: set[str], label: str, errors: list[str]) -> None:
    if not isinstance(ref, str) or not ref:
        errors.append(issue(label, label, "required reference is missing", "Populate this field with an ID from the same PaperExtraction."))
        return
    expect(ref in known_ids, issue(ref, label, "reference does not resolve", "Use an ID that exists in the same PaperExtraction."), errors)


def expect_optional_ref(ref: object, known_ids: set[str], message: str, errors: list[str]) -> None:
    if isinstance(ref, str) and ref:
        expect(ref in known_ids, issue(ref, message, "reference does not resolve", "Use an ID that exists in the same PaperExtraction or remove the optional reference."), errors)


def expect_refs(refs: object, known_ids: set[str], message_prefix: str, errors: list[str]) -> None:
    if refs is None:
        return
    if not isinstance(refs, list):
        errors.append(issue(message_prefix, message_prefix, "reference collection must be a list", "Use a JSON list of object IDs."))
        return
    for ref in refs:
        if not isinstance(ref, str) or not ref:
            errors.append(issue(message_prefix, message_prefix, "reference entry must be a non-empty string", "Use object IDs as non-empty strings."))
            continue
        expect(ref in known_ids, issue(ref, message_prefix, "reference does not resolve", "Use an ID that exists in the same PaperExtraction."), errors)


def validate_json_schema(extraction: dict, errors: list[str]) -> bool:
    validator = Draft202012Validator(JSON_SCHEMA, format_checker=FormatChecker())
    schema_errors = sorted(
        validator.iter_errors(extraction),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    for validation_error in schema_errors:
        path = ".".join(str(part) for part in validation_error.absolute_path) or "paper_extraction"
        errors.append(
            issue(
                path,
                path,
                f"LinkML-derived schema violation: {validation_error.message}",
                "Conform the artifact to skills/csag-extraction/assets/csag.yaml.",
            )
        )
    return not schema_errors


def validate_nested_artifact_refs(value: object, artifact_ids: set[str], path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        if "artifact_ref" in value:
            expect_optional_ref(
                value.get("artifact_ref"),
                artifact_ids,
                f"{path}.artifact_ref references missing id {value.get('artifact_ref')}",
                errors,
            )
        if "associated_artifacts" in value:
            expect_refs(value.get("associated_artifacts"), artifact_ids, f"{path}.associated_artifacts", errors)
        for key, item in value.items():
            validate_nested_artifact_refs(item, artifact_ids, f"{path}.{key}", errors)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            validate_nested_artifact_refs(item, artifact_ids, f"{path}[{index}]", errors)


def is_limitation_or_speculation(assertion: dict) -> bool:
    return assertion.get("claim_role") in {"limitation", "speculation"}


def validate_optional_assertion_metadata(extraction: dict, errors: list[str]) -> None:
    for item in extraction.get("assertions", []) or []:
        if not isinstance(item, dict):
            continue
        criticality = item.get("criticality")
        if criticality is not None:
            expect(
                criticality in ASSERTION_CRITICALITIES,
                issue(
                    item.get("id"),
                    "assertions[].criticality",
                    f"invalid criticality {criticality}",
                    "Use core, major, supporting, or background.",
                ),
                errors,
            )
        falsification_criteria = item.get("falsification_criteria")
        if falsification_criteria is not None:
            expect(
                nonempty_string_list(falsification_criteria),
                issue(
                    item.get("id"),
                    "assertions[].falsification_criteria",
                    "invalid falsification_criteria",
                    "Use a JSON list of one or more concrete falsification criteria strings.",
                ),
                errors,
            )


def validate_cross_references(extraction: dict, ids_by_key: dict[str, set[str]], errors: list[str]) -> None:
    assertion_ids = ids_by_key.get("assertions", set())
    evidence_ids = ids_by_key.get("evidence_items", set())
    evidence_link_ids = ids_by_key.get("evidence_links", set())
    artifact_ids = ids_by_key.get("artifacts", set())
    experiment_ids = ids_by_key.get("experiments", set())
    knowledge_gap_ids = ids_by_key.get("knowledge_gaps", set())
    next_action_ids = ids_by_key.get("next_actions", set())

    validate_nested_artifact_refs(extraction, artifact_ids, "paper_extraction", errors)

    for item in extraction.get("evidence_items", []) or []:
        expect_optional_ref(
            item.get("associated_experiment"),
            experiment_ids,
            f"evidence_item {item.get('id')} references missing associated_experiment {item.get('associated_experiment')}",
            errors,
        )

    for item in extraction.get("evidence_links", []) or []:
        expect_required_ref(
            item.get("evidence_item"),
            evidence_ids,
            f"evidence_link {item.get('id')} evidence_item",
            errors,
        )
        expect_required_ref(
            item.get("assertion"),
            assertion_ids,
            f"evidence_link {item.get('id')} assertion",
            errors,
        )

    for item in extraction.get("inferences", []) or []:
        expect_required_ref(
            item.get("output_assertion"),
            assertion_ids,
            f"inference {item.get('id')} output_assertion",
            errors,
        )
        expect_refs(
            item.get("input_assertions"),
            assertion_ids,
            f"inference {item.get('id')} input_assertions",
            errors,
        )
        expect_refs(
            item.get("input_evidence_links"),
            evidence_link_ids,
            f"inference {item.get('id')} input_evidence_links",
            errors,
        )

    for item in extraction.get("assertion_relations", []) or []:
        expect_required_ref(
            item.get("from_assertion"),
            assertion_ids,
            f"assertion_relation {item.get('id')} from_assertion",
            errors,
        )
        expect_required_ref(
            item.get("to_assertion"),
            assertion_ids,
            f"assertion_relation {item.get('id')} to_assertion",
            errors,
        )
        relation_type = item.get("relation_type")
        if relation_type is not None:
            expect(
                relation_type in ASSERTION_RELATION_TYPES,
                issue(item.get("id"), "assertion_relations[].relation_type", "invalid assertion relation type", "Use a current AssertionRelationType value."),
                errors,
            )

    for item in extraction.get("critiques", []) or []:
        expect_refs(
            item.get("impacted_assertions"),
            assertion_ids,
            f"critique {item.get('id')} impacted_assertions",
            errors,
        )
        expect_refs(
            item.get("impacted_evidence_items"),
            evidence_ids,
            f"critique {item.get('id')} impacted_evidence_items",
            errors,
        )

    for item in extraction.get("knowledge_gaps", []) or []:
        expect_refs(
            item.get("related_assertions"),
            assertion_ids,
            f"knowledge_gap {item.get('id')} related_assertions",
            errors,
        )

    for item in extraction.get("qa_items", []) or []:
        expect_optional_ref(
            item.get("query_assertion"),
            assertion_ids,
            f"qa_item {item.get('id')} references missing query_assertion {item.get('query_assertion')}",
            errors,
        )
        for answer in item.get("answers", []) or []:
            expect_refs(
                answer.get("supporting_assertions"),
                assertion_ids,
                f"qa_item {item.get('id')} answer supporting_assertions",
                errors,
            )
            expect_refs(
                answer.get("supporting_evidence_links"),
                evidence_link_ids,
                f"qa_item {item.get('id')} answer supporting_evidence_links",
                errors,
            )

    for item in extraction.get("research_states", []) or []:
        state = item.get("state")
        expect(bool(item.get("id")), issue(item.get("id"), "research_states[].id", "research state ID is missing", "Assign a deterministic ResearchStateRecord ID."), errors)
        expect(state in RESEARCH_STATES, issue(item.get("id"), "research_states[].state", "missing or invalid research state", "Use open, supported, rejected, mixed, needs_evidence, needs_replication, blocked, or merged."), errors)
        expect_refs(item.get("target_assertions"), assertion_ids, f"research_state {item.get('id')} target_assertions", errors)
        expect_refs(item.get("recommended_next_actions"), next_action_ids, f"research_state {item.get('id')} recommended_next_actions", errors)

    for item in extraction.get("next_actions", []) or []:
        action_type = item.get("action_type")
        priority = item.get("priority")
        expect(bool(item.get("id")), issue(item.get("id"), "next_actions[].id", "next action ID is missing", "Assign a deterministic NextAction ID."), errors)
        expect(action_type in NEXT_ACTION_TYPES, issue(item.get("id"), "next_actions[].action_type", "missing or invalid next action type", "Use a current NextActionType value."), errors)
        expect(bool(item.get("description")), issue(item.get("id"), "next_actions[].description", "missing next action description", "Describe the concrete next experiment, analysis, review, decision, branch, or merge."), errors)
        if priority is not None:
            expect(priority in STRENGTH_LEVELS, issue(item.get("id"), "next_actions[].priority", "invalid priority", "Use one of the StrengthLevel values."), errors)
        expect_refs(item.get("target_assertions"), assertion_ids, f"next_action {item.get('id')} target_assertions", errors)
        expect_refs(item.get("target_knowledge_gaps"), knowledge_gap_ids, f"next_action {item.get('id')} target_knowledge_gaps", errors)

    for item in extraction.get("executions", []) or []:
        status = item.get("execution_status")
        expect(bool(item.get("id")), issue(item.get("id"), "executions[].id", "execution ID is missing", "Assign a deterministic Execution ID."), errors)
        expect(bool(item.get("execution_type")), issue(item.get("id"), "executions[].execution_type", "missing execution type", "Describe the run type, such as benchmark, notebook, analysis script, simulation, or assay."), errors)
        expect(status in EXECUTION_STATUSES, issue(item.get("id"), "executions[].execution_status", "missing or invalid execution status", "Use planned, running, completed, failed, cancelled, or blocked."), errors)
        expect_refs(item.get("output_artifacts"), artifact_ids, f"execution {item.get('id')} output_artifacts", errors)
        expect_refs(item.get("generated_evidence_items"), evidence_ids, f"execution {item.get('id')} generated_evidence_items", errors)
        expect_refs(item.get("tested_assertions"), assertion_ids, f"execution {item.get('id')} tested_assertions", errors)


def validate_semantic_field_placement(extraction: dict, errors: list[str]) -> None:
    placement_rules = {
        "polarity": {"evidence_links"},
        "relation_type": {"assertion_relations"},
        "inference_method": {"inferences"},
        "inference_rationale": {"inferences"},
        "input_assertions": {"inferences"},
        "input_evidence_links": {"inferences"},
        "output_assertion": {"inferences"},
    }
    for collection in ID_LIST_KEYS:
        for item in extraction.get(collection, []) or []:
            if not isinstance(item, dict):
                continue
            for field, allowed_collections in placement_rules.items():
                if field in item and collection not in allowed_collections:
                    errors.append(
                        issue(
                            item.get("id"),
                            f"{collection}[].{field}",
                            "semantic field is recorded on the wrong object type",
                            f"Move {field} to {', '.join(sorted(allowed_collections))}.",
                        )
                    )


def validate_promoted_claim_profile(extraction: dict, ids_by_key: dict[str, set[str]], errors: list[str]) -> None:
    review_activities = [
        activity
        for activity in extraction.get("extraction_activities", []) or []
        if isinstance(activity, dict)
        and re.search(r"\b(human review|curation|curator review)\b", str(activity.get("activity_type", "")), re.IGNORECASE)
    ]
    expect(
        bool(review_activities),
        issue(
            extraction.get("id"),
            "extraction_activities[].activity_type",
            "missing promotion review provenance",
            "Record an ExtractionActivity whose activity_type names human review or curation before using the promoted_claim profile.",
        ),
        errors,
    )

    evidence_by_id = {
        item.get("id"): item
        for item in extraction.get("evidence_items", []) or []
        if isinstance(item, dict) and item.get("id")
    }
    links_by_assertion: dict[str, list[dict]] = {}
    for link in extraction.get("evidence_links", []) or []:
        if not isinstance(link, dict):
            continue
        assertion_id = link.get("assertion")
        if isinstance(assertion_id, str):
            links_by_assertion.setdefault(assertion_id, []).append(link)
        expect(
            link.get("strength") in STRENGTH_LEVELS,
            issue(link.get("id"), "evidence_links[].strength", "missing or invalid strength", "Use one of the StrengthLevel values."),
            errors,
        )
        expect(
            bool(link.get("rationale")),
            issue(link.get("id"), "evidence_links[].rationale", "missing rationale", "Explain why this evidence supports, refutes, or qualifies the assertion."),
            errors,
        )
        expect(
            link.get("polarity") in POLARITIES,
            issue(link.get("id"), "evidence_links[].polarity", "invalid polarity", "Use supports, refutes, mixed, or inconclusive."),
            errors,
        )
        expect(
            link.get("curation_status") in PROMOTED_CURATION_STATUSES,
            issue(link.get("id"), "evidence_links[].curation_status", "missing human curation status", "Use human_verified or human_corrected before promoting the link."),
            errors,
        )

    for assertion in extraction.get("assertions", []) or []:
        if not isinstance(assertion, dict):
            continue
        assertion_id = assertion.get("id")
        criticality = assertion.get("criticality")
        links = links_by_assertion.get(assertion_id, [])
        linked_evidence = [evidence_by_id.get(link.get("evidence_item")) for link in links]

        expect(
            criticality in ASSERTION_CRITICALITIES,
            issue(assertion_id, "assertions[].criticality", "missing or invalid criticality", "Use core, major, supporting, or background."),
            errors,
        )
        expect(
            nonempty_string_list(assertion.get("falsification_criteria")),
            issue(assertion_id, "assertions[].falsification_criteria", "missing falsification criteria", "Add at least one concrete observation or analysis that would weaken the claim."),
            errors,
        )
        expect(
            assertion.get("curation_status") in PROMOTED_CURATION_STATUSES,
            issue(assertion_id, "assertions[].curation_status", "missing human curation status", "Use human_verified or human_corrected before promoting the assertion."),
            errors,
        )
        if criticality != "background":
            expect(
                bool(links),
                issue(assertion_id, "evidence_links", "no evidence links target this assertion", "Add at least one EvidenceLink from a supporting or refuting EvidenceItem."),
                errors,
            )
            expect(
                any(link.get("polarity") in DECISIVE_POLARITIES for link in links),
                issue(assertion_id, "evidence_links[].polarity", "no decisive evidence link", "At least one linked evidence item should use supports, refutes, or mixed."),
                errors,
            )
            expect(
                has_text_spans(assertion) or any(has_text_spans(item) for item in linked_evidence),
                issue(assertion_id, "assertions[].text_spans", "missing assertion/evidence grounding", "Add TextSpan grounding on the assertion or one of its linked EvidenceItems."),
                errors,
            )


def validate_benchmark_key_profile(extraction: dict, ids_by_key: dict[str, set[str]], errors: list[str]) -> None:
    validate_promoted_claim_profile(extraction, ids_by_key, errors)

    links_by_assertion: dict[str, list[dict]] = {}
    for link in extraction.get("evidence_links", []) or []:
        if isinstance(link, dict) and isinstance(link.get("assertion"), str):
            links_by_assertion.setdefault(link["assertion"], []).append(link)

    for assertion in extraction.get("assertions", []) or []:
        if not isinstance(assertion, dict):
            continue
        assertion_id = assertion.get("id")
        criticality = assertion.get("criticality")
        links = links_by_assertion.get(assertion_id, [])
        if criticality in {"core", "major"} and not is_limitation_or_speculation(assertion):
            expect(
                any(
                    link.get("polarity") in DECISIVE_POLARITIES
                    and link.get("strength") in ADEQUATE_STRENGTH_LEVELS
                    for link in links
                ),
                issue(assertion_id, "evidence_links[].strength", "core or major assertion has no moderate-or-strong decisive evidence", "Add a decisive EvidenceLink with strength moderate, strong, or very_strong, or lower the assertion criticality if justified."),
                errors,
            )


def iter_context_ids(extraction: dict) -> set[str]:
    context_ids: set[str] = set()

    def walk(value: object) -> None:
        if isinstance(value, dict):
            item_id = value.get("id")
            if isinstance(item_id, str) and item_id.startswith("csag:context/"):
                context_ids.add(item_id)
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(extraction)
    return context_ids


def validate_context_refs(item: dict, field: str, known_context_ids: set[str], errors: list[str]) -> None:
    contexts = item.get(field)
    if not isinstance(contexts, list) or not contexts:
        errors.append(issue(item.get("id"), f"{field}", "missing contexts", "Attach at least one Context object or context ID."))
        return
    for context in contexts:
        if isinstance(context, dict):
            context_id = context.get("id")
            expect(bool(context_id), issue(item.get("id"), f"{field}[].id", "context ID is missing", "Assign deterministic Context IDs."), errors)
            if context_id:
                expect(context_id in known_context_ids, issue(context_id, field, "context reference does not resolve", "Use a Context ID that exists in the same PaperExtraction."), errors)
            facet = context.get("context_facet")
            if facet is not None:
                expect(facet in CONTEXT_FACETS, issue(context_id, "contexts[].context_facet", "invalid ContextFacet", "Use one of: " + ", ".join(sorted(CONTEXT_FACETS)) + "."), errors)
        elif isinstance(context, str):
            expect(context in known_context_ids, issue(context, field, "context reference does not resolve", "Use a Context ID that exists in the same PaperExtraction."), errors)
        else:
            errors.append(issue(item.get("id"), field, "invalid context reference", "Use context objects or context ID strings."))


def validate_lite_profile(extraction: dict, ids_by_key: dict[str, set[str]], errors: list[str]) -> None:
    context_ids = iter_context_ids(extraction)
    expect(bool(context_ids), issue(extraction.get("id"), "contexts", "missing Context", "Add at least one Context object referenced by an Assertion."), errors)
    expect(len(extraction.get("assertions", []) or []) >= 1, issue(extraction.get("id"), "assertions", "missing Assertion", "Add at least one Assertion."), errors)
    expect(len(extraction.get("evidence_items", []) or []) >= 1, issue(extraction.get("id"), "evidence_items", "missing EvidenceItem", "Add at least one EvidenceItem."), errors)
    expect(len(extraction.get("evidence_links", []) or []) >= 1, issue(extraction.get("id"), "evidence_links", "missing EvidenceLink", "Add at least one EvidenceLink."), errors)

    for assertion in extraction.get("assertions", []) or []:
        if not isinstance(assertion, dict):
            continue
        validate_context_refs(assertion, "contexts", context_ids, errors)
        expect(has_text_spans(assertion), issue(assertion.get("id"), "assertions[].text_spans", "missing source text span", "Ground central Lite assertions with at least one TextSpan."), errors)
    for evidence in extraction.get("evidence_items", []) or []:
        if not isinstance(evidence, dict):
            continue
        expect(bool(evidence.get("id")), issue(evidence.get("id"), "evidence_items[].id", "evidence item ID is missing", "Assign a deterministic EvidenceItem ID."), errors)
        expect(has_text_spans(evidence), issue(evidence.get("id"), "evidence_items[].text_spans", "missing source text span", "Ground central Lite evidence items with at least one TextSpan."), errors)
    for link in extraction.get("evidence_links", []) or []:
        if not isinstance(link, dict):
            continue
        expect(bool(link.get("id")), issue(link.get("id"), "evidence_links[].id", "evidence link ID is missing", "Assign a deterministic EvidenceLink ID."), errors)
        expect(bool(link.get("evidence_item")), issue(link.get("id"), "evidence_links[].evidence_item", "missing evidence item reference", "Reference an EvidenceItem ID."), errors)
        expect(bool(link.get("assertion")), issue(link.get("id"), "evidence_links[].assertion", "missing assertion reference", "Reference an Assertion ID."), errors)


def validate_module_profiles(extraction: dict, modules: set[str], warnings: list[str]) -> None:
    """Emit non-blocking guidance for optional CSAG module profiles.

    The core profile is mandatory and enforced by the normal paper-local checks.
    The other module profiles are intentionally warnings-first: selecting
    ``core,bio`` or ``core,reasoning`` should make the expected enrichment
    visible without making every paper fail just because a source lacks that
    enrichment.
    """
    if "bio" in modules:
        has_bio_layer = any(extraction.get(key) for key in ("entities", "studies")) or any(
            assertion.get("conditions") or assertion.get("qualifiers") or assertion.get("subject") or assertion.get("object")
            for assertion in extraction.get("assertions", []) or []
            if isinstance(assertion, dict)
        )
        if not has_bio_layer:
            warnings.append(
                "profile=bio selected but no entity, study/experiment, condition, qualifier, or normalized assertion fields are populated."
            )

    if "reasoning" in modules:
        has_reasoning_layer = bool(extraction.get("inferences")) or bool(extraction.get("assertion_relations"))
        if not has_reasoning_layer:
            warnings.append(
                "profile=reasoning selected but no inferences or assertion_relations are populated."
            )

    if "research_state" in modules:
        has_research_state_layer = bool(extraction.get("research_states")) or bool(extraction.get("next_actions")) or bool(extraction.get("executions"))
        if not has_research_state_layer:
            warnings.append(
                "profile=research_state selected but no research_states, next_actions, or executions are populated."
            )

    if "benchmark" in modules:
        has_benchmark_layer = bool(extraction.get("qa_items")) or bool(extraction.get("assertions"))
        if not has_benchmark_layer:
            warnings.append(
                "profile=benchmark selected but no assertions or qa_items are populated for scoring."
            )


def main() -> int:
    args = parse_args()
    profile, strictness_profile, module_profiles, profile_errors = parse_profile(args.profile)
    extraction_path = args.extraction_json.expanduser().resolve()
    validated_extraction_path = extraction_path
    report_path = args.report_out.expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    source_path = args.source_markdown.expanduser().resolve() if args.source_markdown else None
    article_path = args.article_json.expanduser().resolve() if args.article_json else None
    inputs = input_records(
        base_dir=report_path.parent,
        extraction=extraction_path,
        source_markdown=source_path,
        article_json=article_path,
    )
    extraction = load_json(extraction_path)
    article = load_json(args.article_json)
    source_markdown = (
        args.source_markdown.expanduser().resolve().read_text(encoding="utf-8")
        if args.source_markdown
        else ""
    )
    repair_actions: list[dict[str, Any]] = []
    if isinstance(extraction, dict) and args.repair_out:
        extraction, repair_actions = repair_paper_extraction(extraction)
        repaired_path = args.repair_out.expanduser().resolve()
        repaired_path.parent.mkdir(parents=True, exist_ok=True)
        repaired_path.write_text(
            json.dumps(extraction, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        validated_extraction_path = repaired_path
        inputs = input_records(
            base_dir=report_path.parent,
            extraction=repaired_path,
            source_markdown=source_path,
            article_json=article_path,
        )
        if repaired_path != extraction_path:
            inputs["source_extraction"] = input_record(
                extraction_path,
                base_dir=report_path.parent,
            )

    errors: list[str] = []
    warnings: list[str] = []
    errors.extend(profile_errors)

    expect(
        isinstance(extraction, dict),
        issue("(input)", "paper_extraction", "paper extraction is not a JSON object", "Provide a PaperExtraction JSON object."),
        errors,
    )
    if errors:
        return write_report(
            report_path,
            validated_extraction_path,
            False,
            errors,
            warnings,
            {},
            profile,
            repair_actions,
            strictness_profile=strictness_profile,
            profile_modules=module_profiles,
            inputs=inputs,
        )

    root_id = extraction.get("id") or "(paper extraction)"
    schema_valid = validate_json_schema(extraction, errors)
    if not schema_valid:
        return write_report(
            report_path,
            validated_extraction_path,
            False,
            errors,
            warnings,
            {},
            profile,
            repair_actions,
            strictness_profile=strictness_profile,
            profile_modules=module_profiles,
            inputs=inputs,
        )
    expect(bool(extraction.get("id")), issue(root_id, "id", "missing top-level id", "Set the PaperExtraction document ID."), errors)
    expect(bool(extraction.get("title")), issue(root_id, "title", "missing top-level title", "Set the manuscript title."), errors)
    expect(bool(extraction.get("schema_version")), issue(root_id, "schema_version", "missing schema version", "Set the CSAG schema version used for the extraction."), errors)
    expect(bool(extraction.get("validator_version")), issue(root_id, "validator_version", "missing validator version", "Set the validator version used for the validation report."), errors)
    expect(isinstance(extraction.get("assertions"), list), issue(root_id, "assertions", "missing assertions list", "Add an assertions array, even if empty only for non-paper material."), errors)
    expect(isinstance(extraction.get("evidence_items"), list), issue(root_id, "evidence_items", "missing evidence_items list", "Add an evidence_items array."), errors)
    expect(isinstance(extraction.get("evidence_links"), list), issue(root_id, "evidence_links", "missing evidence_links list", "Add an evidence_links array."), errors)
    if strictness_profile != "lite":
        expect(isinstance(extraction.get("extraction_activities"), list) and extraction.get("extraction_activities"), issue(root_id, "extraction_activities", "missing extraction activities", "Record at least one extraction activity with DOI/PMID status parameters."), errors)

    ids_by_key = collect_ids(extraction, errors)

    for item in extraction.get("assertions", []):
        assertion_id = item.get("id")
        expect(bool(assertion_id), issue(assertion_id, "assertions[].id", "assertion ID is missing", "Assign a deterministic assertion ID."), errors)
        expect(bool(item.get("assertion_text")), issue(assertion_id, "assertions[].assertion_text", "missing assertion text", "Add the natural-language assertion."), errors)
        expect(bool(item.get("claim_role")), issue(assertion_id, "assertions[].claim_role", "missing claim role", "Set claim_role from the controlled vocabulary."), errors)
        if item.get("claim_role"):
            expect(
                item.get("claim_role") in CLAIM_ROLES,
                issue(assertion_id, "assertions[].claim_role", "invalid claim role", "Set claim_role from the controlled vocabulary."),
                errors,
            )
        expect(bool(item.get("normalization_status")), issue(assertion_id, "assertions[].normalization_status", "missing normalization status", "Set raw, partially_normalized, or fully_normalized."), errors)
        if item.get("normalization_status"):
            expect(
                item.get("normalization_status") in NORMALIZATION_STATUSES,
                issue(assertion_id, "assertions[].normalization_status", "invalid normalization status", "Set raw, partially_normalized, or fully_normalized."),
                errors,
            )
        expect(isinstance(item.get("contexts"), list) and len(item.get("contexts")) >= 1, issue(assertion_id, "assertions[].contexts", "missing contexts", "Attach at least one Context object to every Assertion."), errors)

    for item in extraction.get("evidence_links", []):
        expect(bool(item.get("polarity")), issue(item.get("id"), "evidence_links[].polarity", "missing polarity", "Use supports, refutes, mixed, or inconclusive."), errors)
        if item.get("polarity"):
            expect(
                item.get("polarity") in POLARITIES,
                issue(item.get("id"), "evidence_links[].polarity", "invalid polarity", "Use supports, refutes, mixed, or inconclusive."),
                errors,
            )

    validate_optional_assertion_metadata(extraction, errors)
    validate_semantic_field_placement(extraction, errors)
    validate_cross_references(extraction, ids_by_key, errors)
    validate_module_profiles(extraction, module_profiles, warnings)
    if strictness_profile == "lite":
        validate_lite_profile(extraction, ids_by_key, errors)
    if strictness_profile == "promoted_claim":
        validate_promoted_claim_profile(extraction, ids_by_key, errors)
    if strictness_profile == "benchmark_key":
        validate_benchmark_key_profile(extraction, ids_by_key, errors)

    if strictness_profile != "lite":
        param_map = collect_parameter_map(extraction)
        source_text = front_matter_only(source_markdown)
        if article is not None:
            source_text += "\n" + article.get("title", "")
            source_text += "\n" + article.get("authors", "")
            source_text += "\n" + article.get("affiliations", "")
            source_text += "\n" + article.get("abstract", "")

        source_doi = DOI_RE.search(source_text)
        source_pmid = PMID_RE.search(source_text)
        doi = extraction.get("doi", "")
        pmid = extraction.get("pmid", "")
        doi_status = param_map.get("doi_status")
        pmid_status = param_map.get("pmid_status")

        if source_doi:
            expect(bool(doi), issue(root_id, "doi", "DOI appears recoverable from the source but extraction.doi is empty", "Populate extraction.doi from the source or remove the incorrect DOI signal from the sidecar."), errors)
        else:
            expect(doi_status in {"resolved", "unresolved"}, issue(root_id, "extraction_activities[].parameters.doi_status", "missing explicit DOI status", "Record doi_status as resolved or unresolved in extraction activity parameters."), errors)
        if doi:
            expect(doi_status in {None, "resolved"}, issue(root_id, "extraction_activities[].parameters.doi_status", "extraction.doi is populated but doi_status is not resolved", "Set doi_status to resolved when extraction.doi is populated."), errors)

        if source_pmid:
            expect(bool(pmid), issue(root_id, "pmid", "PMID appears recoverable from the source but extraction.pmid is empty", "Populate extraction.pmid from the source or remove the incorrect PMID signal from the sidecar."), errors)
        else:
            expect(pmid_status in {"resolved", "unresolved"}, issue(root_id, "extraction_activities[].parameters.pmid_status", "missing explicit PMID status", "Record pmid_status as resolved or unresolved in extraction activity parameters."), errors)
        if pmid:
            expect(pmid_status in {None, "resolved"}, issue(root_id, "extraction_activities[].parameters.pmid_status", "extraction.pmid is populated but pmid_status is not resolved", "Set pmid_status to resolved when extraction.pmid is populated."), errors)

        figure_legends = article.get("figure_legends", []) if isinstance(article, dict) else []
        figure_signals = bool(figure_legends)
        if not figure_signals and source_markdown:
            figure_signals = any(FIGURE_SIGNAL_RE.match(line) for line in source_markdown.splitlines())
        if figure_signals:
            artifacts = extraction.get("artifacts", [])
            expect(isinstance(artifacts, list) and len(artifacts) > 0, issue(root_id, "artifacts", "figure/table captions are present in the source but extraction.artifacts is empty", "Add Artifact entries for source figures or tables, or correct the article sidecar if captions were detected incorrectly."), errors)
            for artifact in artifacts:
                artifact_id = artifact.get("id")
                expect(bool(artifact_id), issue(artifact_id, "artifacts[].id", "artifact ID is missing", "Assign a deterministic Artifact ID."), errors)
                expect(bool(artifact.get("artifact_type")), issue(artifact_id, "artifacts[].artifact_type", "missing artifact type", "Set artifact_type from the controlled vocabulary."), errors)
                if artifact.get("artifact_type"):
                    expect(
                        artifact.get("artifact_type") in ARTIFACT_TYPES,
                        issue(artifact_id, "artifacts[].artifact_type", "invalid artifact type", "Use figure, table, supplementary, equation, protocol, code, or other."),
                        errors,
                    )
                expect(bool(artifact.get("artifact_label")) or bool(artifact.get("caption")), issue(artifact_id, "artifacts[].artifact_label", "missing artifact label or caption", "Populate artifact_label or caption from the source."), errors)

        dataset_signals = bool(source_markdown and DATASET_SIGNAL_RE.search(source_markdown))
        if dataset_signals:
            datasets = extraction.get("datasets", [])
            expect(isinstance(datasets, list) and len(datasets) > 0, issue(root_id, "datasets", "dataset/data-availability signals are present in the source but extraction.datasets is empty", "Add Dataset entries for accessions or repositories mentioned by the source, or correct the source sidecar if the signal was detected incorrectly."), errors)
            for dataset in datasets:
                dataset_id = dataset.get("id")
                expect(bool(dataset_id), issue(dataset_id, "datasets[].id", "dataset ID is missing", "Assign a deterministic Dataset ID."), errors)
                expect(
                    bool(dataset.get("accession")) or bool(dataset.get("repository")) or bool(dataset.get("dataset_url")),
                    issue(dataset_id, "datasets[].accession", "missing accession, repository, or dataset URL", "Populate accession, repository, or dataset_url from the source data-availability statement."),
                    errors,
                )

    report = {
        "ok": not errors,
        "profile": profile,
        "strictness_profile": strictness_profile,
        "profile_modules": ordered_modules(module_profiles),
        "validator_version": VALIDATOR_VERSION,
        "extraction_json": str(inputs["extraction"]["path"]),
        "inputs": inputs,
        "errors": errors,
        "structured_errors": [structured_issue(error) for error in errors],
        "error_summary": error_summary(errors),
        "warnings": warnings,
        "repair_actions": repair_actions,
        "metrics": {
            "assertions": len(extraction.get("assertions", [])),
            "assertions_with_criticality": sum(
                1 for item in extraction.get("assertions", []) if item.get("criticality")
            ),
            "assertions_with_falsification_criteria": sum(
                1 for item in extraction.get("assertions", []) if nonempty_string_list(item.get("falsification_criteria"))
            ),
            "evidence_items": len(extraction.get("evidence_items", [])),
            "evidence_links": len(extraction.get("evidence_links", [])),
            "artifacts": len(extraction.get("artifacts", [])),
            "datasets": len(extraction.get("datasets", [])),
        },
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK")
    return 0


def write_report(
    report_path: Path,
    extraction_path: Path,
    ok: bool,
    errors: list[str],
    warnings: list[str],
    metrics: dict,
    profile: str = "candidate",
    repair_actions: list[dict[str, Any]] | None = None,
    *,
    strictness_profile: str | None = None,
    profile_modules: set[str] | None = None,
    inputs: dict[str, dict[str, object]] | None = None,
) -> int:
    input_map = inputs or {}
    extraction_label = input_map.get("extraction", {}).get("path", str(extraction_path))
    report = {
        "ok": ok,
        "profile": profile,
        "strictness_profile": strictness_profile or profile,
        "profile_modules": ordered_modules(profile_modules or {"core"}),
        "validator_version": VALIDATOR_VERSION,
        "extraction_json": str(extraction_label),
        "inputs": input_map,
        "errors": errors,
        "structured_errors": [structured_issue(error) for error in errors],
        "error_summary": error_summary(errors),
        "warnings": warnings,
        "repair_actions": repair_actions or [],
        "metrics": metrics,
    }
    resolved_report_path = report_path.expanduser().resolve()
    resolved_report_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
