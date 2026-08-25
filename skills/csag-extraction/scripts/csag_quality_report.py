#!/usr/bin/env python3
"""CSAG quality report.

Reads a `paper_extraction.json` (CSAG `PaperExtraction`) and prints a quality
report covering coverage, grounding, normalization, and structural integrity.
Optionally writes the same report to a JSON file for downstream tooling.

This is complementary to `validate_paper_extraction.py`:
- `validate_paper_extraction.py` enforces correctness (errors fail the run).
- `csag_quality_report.py` summarizes shape, coverage, and gaps without failing.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from csag_provenance import input_records

WORD_RE = re.compile(r"\w+", re.UNICODE)
DATASET_SIGNAL_RE = re.compile(
    r"\b(data availability|accession|project id|repository|zenodo|img/m|data portal|sra|geo|pride|available at|downloaded at)\b",
    re.IGNORECASE,
)
FIGURE_SIGNAL_RE = re.compile(
    r"^\s*(fig(?:ure)?\.?|table|supplementary figure|supplementary table)\b",
    re.IGNORECASE | re.MULTILINE,
)

ASSERTION_CRITICALITIES = ("core", "major", "supporting", "background")
CLAIM_ROLES = (
    "background",
    "hypothesis",
    "research_question",
    "objective",
    "method_claim",
    "result_claim",
    "conclusion",
    "discovery",
    "speculation",
    "limitation",
    "future_work",
)
NORMALIZATION_STATUSES = ("raw", "partially_normalized", "fully_normalized")
POLARITIES = ("supports", "refutes", "mixed", "inconclusive")
STRENGTHS = ("very_strong", "strong", "moderate", "weak", "very_weak", "unknown")
SECTION_TYPES = (
    "title",
    "abstract",
    "introduction",
    "methods",
    "results",
    "discussion",
    "conclusion",
    "supplementary",
    "figure_caption",
    "table_caption",
    "other",
)
RESEARCH_STATES = ("open", "supported", "rejected", "mixed", "needs_evidence", "needs_replication", "blocked", "merged")
EMPIRICAL_EVIDENCE_TYPES = {
    "experimental_result",
    "statistical_analysis",
    "computational_model",
    "observational_data",
    "replication",
    "control_result",
    "negative_result",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report CSAG quality stats for a PaperExtraction.")
    parser.add_argument("extraction_json", type=Path, help="Path to paper_extraction.json")
    parser.add_argument(
        "--source-markdown",
        type=Path,
        default=None,
        help="Optional canonical Markdown to count words per section.",
    )
    parser.add_argument(
        "--article-json",
        type=Path,
        default=None,
        help="Optional article sidecar to detect figure/table and dataset signals.",
    )
    parser.add_argument(
        "--report-out",
        type=Path,
        default=None,
        help="Optional path to write the JSON report.",
    )
    parser.add_argument(
        "--document-scope",
        choices=("lite", "short_note", "full_article", "benchmark_key", "auto"),
        default="auto",
        help="Extraction-density scope used for completeness targets.",
    )
    parser.add_argument(
        "--openalex-json",
        type=Path,
        default=None,
        help="Optional saved OpenAlex Work JSON used for literature-quality context. No network calls are made.",
    )
    parser.add_argument(
        "--analysis-year",
        type=int,
        default=date.today().year,
        help="Year used for age-normalized citation metrics.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when structural issues or strict density failures are detected.",
    )
    return parser.parse_args()


def count_words(text: str) -> int:
    return len(WORD_RE.findall(text or ""))


def count_words_per_section(markdown: str) -> dict[str, int]:
    """Group word counts by `## heading` blocks. Headings before the first `##` go to `_preamble`."""
    counts: dict[str, int] = {}
    if not markdown:
        return counts
    current = "_preamble"
    buffer: list[str] = []
    for line in markdown.splitlines():
        match = re.match(r"^##+\s+(.+?)\s*$", line.strip())
        if match:
            counts[current] = counts.get(current, 0) + count_words("\n".join(buffer))
            buffer = []
            current = match.group(1).strip()
            continue
        buffer.append(line)
    counts[current] = counts.get(current, 0) + count_words("\n".join(buffer))
    return {key: value for key, value in counts.items() if value > 0}


def safe_list(extraction: dict, key: str) -> list[dict]:
    items = extraction.get(key)
    return items if isinstance(items, list) else []


def value_distribution(items: list[dict], field: str, allowed: tuple[str, ...]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get(field)
        if isinstance(value, str):
            counter[value] += 1
    return {key: counter.get(key, 0) for key in allowed} | {
        f"_other:{name}": counter[name]
        for name in counter
        if name not in allowed
    }


def text_span_coverage(items: list[dict]) -> dict[str, int]:
    grounded = sum(
        1
        for item in items
        if isinstance(item, dict) and isinstance(item.get("text_spans"), list) and item.get("text_spans")
    )
    return {"with_text_spans": grounded, "without_text_spans": len(items) - grounded}


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def text_word_count(value: Any) -> int:
    if isinstance(value, str):
        return count_words(value)
    if isinstance(value, list):
        return sum(text_word_count(item) for item in value)
    if isinstance(value, dict):
        return sum(text_word_count(item) for item in value.values())
    return 0


def json_text_blob(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(json_text_blob(item) for item in value)
    if isinstance(value, dict):
        return "\n".join(json_text_blob(item) for item in value.values())
    return str(value)


def article_signals(article_json: dict | None, source_markdown: str | None) -> dict[str, bool]:
    article_text = json_text_blob(article_json)
    source_text = source_markdown or ""
    combined = "\n".join([article_text, source_text])
    figure_legend_count = 0
    if isinstance(article_json, dict):
        legends = article_json.get("figure_legends")
        if isinstance(legends, list):
            figure_legend_count += len([item for item in legends if has_value(item)])
        tables = article_json.get("tables")
        if isinstance(tables, list):
            figure_legend_count += len([item for item in tables if has_value(item)])
    return {
        "figure_or_table_caption_present": bool(figure_legend_count or FIGURE_SIGNAL_RE.search(combined)),
        "dataset_signal_present": bool(DATASET_SIGNAL_RE.search(combined)),
    }


FIELD_PROFILES: dict[str, dict[str, tuple[str, ...]]] = {
    "assertions": {
        "required": ("id", "assertion_text", "claim_role", "normalization_status", "contexts"),
        "recommended": ("assertion_type", "criticality", "falsification_criteria", "text_spans"),
    },
    "evidence_items": {
        "required": ("id", "evidence_type"),
        "recommended": ("evidence_text", "contexts", "text_spans"),
    },
    "evidence_links": {
        "required": ("id", "evidence_item", "assertion", "polarity"),
        "recommended": ("strength", "rationale", "text_spans"),
    },
    "inferences": {
        "required": ("id", "output_assertion", "inference_method"),
        "recommended": ("input_assertions", "input_evidence_links", "inference_rationale", "text_spans"),
    },
    "critiques": {
        "required": ("id",),
        "recommended": ("critique_type", "risk_domain", "severity", "impacted_assertions", "text_spans"),
    },
    "knowledge_gaps": {
        "required": ("id",),
        "recommended": ("gap_type", "severity", "related_assertions", "suggested_actions", "text_spans"),
    },
    "artifacts": {
        "required": ("id", "artifact_type", "artifact_label"),
        "recommended": ("caption", "text_spans"),
    },
    "datasets": {
        "required": ("id",),
        "recommended": ("accession", "repository", "dataset_url", "text_spans"),
    },
    "qa_items": {
        "required": ("id", "question_text", "expected_answer_type", "answers"),
        "recommended": ("query_assertion", "normalized_query"),
    },
    "research_states": {
        "required": ("id", "state"),
        "recommended": ("target_assertions", "current_read", "rationale", "recommended_next_actions"),
    },
    "next_actions": {
        "required": ("id", "action_type", "description"),
        "recommended": ("target_assertions", "target_knowledge_gaps", "priority"),
    },
    "executions": {
        "required": ("id", "execution_type", "execution_status"),
        "recommended": ("command", "output_artifacts", "generated_evidence_items", "tested_assertions"),
    },
}

TEXT_FIELDS = {
    "assertions": ("assertion_text",),
    "evidence_items": ("evidence_text",),
    "evidence_links": ("rationale",),
    "inferences": ("inference_rationale",),
    "research_states": ("current_read", "rationale"),
    "next_actions": ("description",),
    "executions": ("command",),
}


def field_quality_report(extraction: dict) -> dict:
    collections: dict[str, dict] = {}
    total_required = 0
    missing_required = 0
    total_recommended = 0
    missing_recommended = 0
    weak_text_values: list[dict[str, str]] = []

    for collection, profile in FIELD_PROFILES.items():
        items = safe_list(extraction, collection)
        required = profile["required"]
        recommended = profile["recommended"]
        required_missing_by_field = Counter()
        recommended_missing_by_field = Counter()
        object_reports = []
        for item in items:
            item_id = str(item.get("id") or "(missing id)")
            missing_req = [field for field in required if not has_value(item.get(field))]
            missing_rec = [field for field in recommended if not has_value(item.get(field))]
            for field in missing_req:
                required_missing_by_field[field] += 1
            for field in missing_rec:
                recommended_missing_by_field[field] += 1
            for field in TEXT_FIELDS.get(collection, ()):
                if has_value(item.get(field)) and text_word_count(item.get(field)) < 5:
                    weak_text_values.append(
                        {
                            "object_id": item_id,
                            "field": f"{collection}.{field}",
                            "reason": "text is very short and may be under-informative",
                        }
                    )
            object_reports.append(
                {
                    "id": item_id,
                    "missing_required": missing_req,
                    "missing_recommended": missing_rec,
                }
            )
        collection_required = len(items) * len(required)
        collection_recommended = len(items) * len(recommended)
        collection_missing_required = sum(required_missing_by_field.values())
        collection_missing_recommended = sum(recommended_missing_by_field.values())
        total_required += collection_required
        missing_required += collection_missing_required
        total_recommended += collection_recommended
        missing_recommended += collection_missing_recommended
        denominator = collection_required + collection_recommended
        score = 1.0
        if denominator:
            score = 1 - ((collection_missing_required * 1.0 + collection_missing_recommended * 0.5) / denominator)
        collections[collection] = {
            "object_count": len(items),
            "required_fields": list(required),
            "recommended_fields": list(recommended),
            "missing_required_by_field": dict(required_missing_by_field),
            "missing_recommended_by_field": dict(recommended_missing_by_field),
            "objects_with_missing_required": [
                item for item in object_reports if item["missing_required"]
            ],
            "objects_with_missing_recommended": [
                item for item in object_reports if item["missing_recommended"]
            ],
            "field_completeness_score": round(max(0.0, min(1.0, score)), 3),
        }

    denominator = total_required + total_recommended
    overall = 1.0 if not denominator else 1 - ((missing_required * 1.0 + missing_recommended * 0.5) / denominator)
    return {
        "overall_field_completeness_score": round(max(0.0, min(1.0, overall)), 3),
        "missing_required_field_count": missing_required,
        "missing_recommended_field_count": missing_recommended,
        "weak_text_values": weak_text_values,
        "collections": collections,
    }


def completeness_report(
    extraction: dict,
    counts: dict,
    coverage: dict,
    signals: dict,
    word_counts: dict[str, int],
    document_scope: str = "auto",
) -> dict:
    total_words = sum(word_counts.values())
    resolved_scope = resolve_document_scope(document_scope, total_words, counts)
    compact_source = resolved_scope in {"lite", "short_note"} or bool(total_words and total_words < 1500)
    assertions = safe_list(extraction, "assertions")
    roles = Counter(item.get("claim_role") for item in assertions if isinstance(item, dict))
    result_roles = roles["result_claim"] + roles["conclusion"] + roles["discovery"]
    objective_roles = roles["hypothesis"] + roles["research_question"] + roles["objective"]
    result_target = 1 if compact_source else 2
    evidence_target = 1 if compact_source else 2
    checks = [
        {
            "name": "objective_or_question_assertion",
            "status": "pass" if objective_roles >= 1 else "warn",
            "observed": objective_roles,
            "target": 1,
            "reason": "hypothesis, research question, or objective assertion coverage",
            "suggested_fix": "Add an objective/research-question assertion, or state in notes that the source lacks one.",
        },
        {
            "name": "result_or_conclusion_assertions",
            "status": "pass" if result_roles >= result_target else "warn",
            "observed": result_roles,
            "target": result_target,
            "reason": "result/conclusion claim coverage",
            "suggested_fix": "Extract additional result or conclusion assertions from distinct manuscript sections when present.",
        },
        {
            "name": "evidence_items",
            "status": "pass" if counts["evidence_items"] >= evidence_target else "warn",
            "observed": counts["evidence_items"],
            "target": evidence_target,
            "reason": "evidence item coverage",
            "suggested_fix": "Add evidence items for the main analyses, observations, or cited support.",
        },
        {
            "name": "evidence_links",
            "status": "pass" if counts["evidence_links"] >= evidence_target else "warn",
            "observed": counts["evidence_links"],
            "target": evidence_target,
            "reason": "claim-to-evidence linkage",
            "suggested_fix": "Link each key assertion to supporting, refuting, mixed, or inconclusive evidence.",
        },
        {
            "name": "assertion_contexts",
            "status": "pass" if coverage["assertions_missing_context"] == 0 else "fail",
            "observed": coverage["assertions_with_context"],
            "target": coverage["assertions"],
            "reason": "every assertion needs at least one context",
            "suggested_fix": "Attach a Context object to each assertion.",
        },
        {
            "name": "falsification_criteria",
            "status": "pass" if coverage["assertions_with_falsification_criteria"] >= max(1, result_target) else "warn",
            "observed": coverage["assertions_with_falsification_criteria"],
            "target": max(1, result_target),
            "reason": "core or major claims should say what would weaken them",
            "suggested_fix": "Add falsification criteria to core and major assertions.",
        },
    ]
    if resolved_scope != "lite":
        checks.extend(
            [
                {
                    "name": "artifacts_from_captions",
                    "status": "pass" if not signals["figure_or_table_caption_present"] or counts["artifacts"] > 0 else "fail",
                    "observed": counts["artifacts"],
                    "target": 1 if signals["figure_or_table_caption_present"] else 0,
                    "reason": "figure/table captions in source should be represented as artifacts",
                    "suggested_fix": "Add Artifact objects for detected figures, tables, and supplements.",
                },
                {
                    "name": "datasets_from_availability_signals",
                    "status": "pass" if not signals["dataset_signal_present"] or counts["datasets"] > 0 else "fail",
                    "observed": counts["datasets"],
                    "target": 1 if signals["dataset_signal_present"] else 0,
                    "reason": "data-availability or accession signals should be represented as datasets",
                    "suggested_fix": "Add Dataset objects for repository links, accessions, project IDs, and availability statements.",
                },
            ]
        )
    passed = sum(1 for item in checks if item["status"] == "pass")
    return {
        "document_scope": resolved_scope,
        "requested_document_scope": document_scope,
        "source_word_count": total_words,
        "score": round(passed / len(checks), 3) if checks else 1.0,
        "checks": checks,
    }


def text_span_section_distribution(extraction: dict) -> dict[str, int]:
    counter: Counter[str] = Counter()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            spans = node.get("text_spans")
            if isinstance(spans, list):
                for span in spans:
                    if isinstance(span, dict):
                        section = span.get("section_type") or "unknown"
                        counter[section] += 1
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(extraction)
    return dict(counter)


def collect_ids(items: list[dict]) -> set[str]:
    return {
        item["id"]
        for item in items
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]
    }


def assertion_evidence_coverage(extraction: dict) -> dict[str, int]:
    assertions = safe_list(extraction, "assertions")
    links = safe_list(extraction, "evidence_links")
    by_assertion: dict[str, list[dict]] = {}
    for link in links:
        if isinstance(link, dict) and isinstance(link.get("assertion"), str):
            by_assertion.setdefault(link["assertion"], []).append(link)

    with_links = sum(1 for assertion in assertions if assertion.get("id") in by_assertion)
    decisive_polarities = {"supports", "refutes", "mixed"}
    with_decisive = sum(
        1
        for assertion in assertions
        if any(
            link.get("polarity") in decisive_polarities
            for link in by_assertion.get(assertion.get("id"), [])
        )
    )
    return {
        "assertions": len(assertions),
        "with_evidence_links": with_links,
        "without_evidence_links": len(assertions) - with_links,
        "with_decisive_evidence": with_decisive,
    }


def evidence_link_orphans(extraction: dict) -> dict[str, int]:
    assertion_ids = collect_ids(safe_list(extraction, "assertions"))
    evidence_ids = collect_ids(safe_list(extraction, "evidence_items"))
    dangling_assertion = 0
    dangling_evidence = 0
    for link in safe_list(extraction, "evidence_links"):
        if not isinstance(link, dict):
            continue
        if isinstance(link.get("assertion"), str) and link["assertion"] not in assertion_ids:
            dangling_assertion += 1
        if isinstance(link.get("evidence_item"), str) and link["evidence_item"] not in evidence_ids:
            dangling_evidence += 1
    return {
        "evidence_links_with_unknown_assertion": dangling_assertion,
        "evidence_links_with_unknown_evidence_item": dangling_evidence,
    }


def assertions_with_falsification(extraction: dict) -> int:
    return sum(
        1
        for assertion in safe_list(extraction, "assertions")
        if isinstance(assertion.get("falsification_criteria"), list)
        and any(isinstance(item, str) and item.strip() for item in assertion["falsification_criteria"])
    )


def context_coverage(extraction: dict) -> dict[str, int]:
    assertions = safe_list(extraction, "assertions")
    with_context = sum(
        1
        for assertion in assertions
        if isinstance(assertion.get("contexts"), list) and len(assertion["contexts"]) >= 1
    )
    return {
        "assertions_with_context": with_context,
        "assertions_missing_context": len(assertions) - with_context,
    }


def evidence_text(evidence: dict | None) -> str:
    if not isinstance(evidence, dict):
        return ""
    return str(evidence.get("evidence_text") or evidence.get("description") or evidence.get("label") or "")


def links_by_assertion(extraction: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for link in safe_list(extraction, "evidence_links"):
        if isinstance(link, dict) and isinstance(link.get("assertion"), str):
            grouped.setdefault(link["assertion"], []).append(link)
    return grouped


def research_states_by_assertion(extraction: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for state in safe_list(extraction, "research_states"):
        targets = state.get("target_assertions")
        if isinstance(targets, list):
            for assertion_id in targets:
                if isinstance(assertion_id, str):
                    grouped.setdefault(assertion_id, []).append(state)
    return grouped


def next_actions_by_assertion(extraction: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for action in safe_list(extraction, "next_actions"):
        targets = action.get("target_assertions")
        if isinstance(targets, list):
            for assertion_id in targets:
                if isinstance(assertion_id, str):
                    grouped.setdefault(assertion_id, []).append(action)
    return grouped


def infer_claim_state(links: list[dict]) -> str:
    if not links:
        return "needs_evidence"
    polarities = Counter(link.get("polarity") for link in links)
    if polarities["mixed"] or (polarities["supports"] and polarities["refutes"]):
        return "mixed"
    if polarities["supports"] and not (polarities["refutes"] or polarities["mixed"]):
        return "supported"
    if polarities["refutes"] and not (polarities["supports"] or polarities["mixed"]):
        return "rejected"
    return "open"


def build_claim_readouts(extraction: dict) -> list[dict]:
    evidence_by_id = {
        evidence.get("id"): evidence
        for evidence in safe_list(extraction, "evidence_items")
        if isinstance(evidence, dict) and isinstance(evidence.get("id"), str)
    }
    grouped_links = links_by_assertion(extraction)
    grouped_states = research_states_by_assertion(extraction)
    grouped_actions = next_actions_by_assertion(extraction)
    readouts: list[dict] = []

    def link_summary(link: dict) -> dict:
        evidence = evidence_by_id.get(link.get("evidence_item"))
        return {
            "evidence_link_id": link.get("id"),
            "evidence_item": link.get("evidence_item"),
            "strength": link.get("strength", ""),
            "rationale": link.get("rationale", ""),
            "evidence_text": evidence_text(evidence),
            "associated_artifacts": evidence.get("associated_artifacts", []) if isinstance(evidence, dict) else [],
            "results": evidence.get("results", []) if isinstance(evidence, dict) else [],
        }

    for assertion in safe_list(extraction, "assertions"):
        if not isinstance(assertion, dict):
            continue
        assertion_id = assertion.get("id")
        links = grouped_links.get(assertion_id, [])
        states = grouped_states.get(assertion_id, [])
        state_record = states[0] if states else {}
        current_state = state_record.get("state") or infer_claim_state(links)
        current_read = state_record.get("current_read") or (
            "No evidence link is attached; the claim needs evidence."
            if current_state == "needs_evidence"
            else f"Inferred from {len(links)} evidence link(s): {current_state}."
        )
        actions = grouped_actions.get(assertion_id, [])
        readouts.append(
            {
                "assertion_id": assertion_id,
                "claim_role": assertion.get("claim_role", ""),
                "criticality": assertion.get("criticality", ""),
                "assertion_text": assertion.get("assertion_text", ""),
                "state": current_state,
                "current_read": current_read,
                "evidence_for": [link_summary(link) for link in links if link.get("polarity") == "supports"],
                "evidence_against": [link_summary(link) for link in links if link.get("polarity") == "refutes"],
                "mixed_or_inconclusive": [
                    link_summary(link)
                    for link in links
                    if link.get("polarity") in {"mixed", "inconclusive"}
                ],
                "next_actions": [
                    {
                        "id": action.get("id"),
                        "action_type": action.get("action_type", ""),
                        "description": action.get("description", ""),
                        "priority": action.get("priority", ""),
                    }
                    for action in actions
                ],
                "research_state_records": [state.get("id") for state in states if state.get("id")],
            }
        )
    return readouts


def artifact_discipline_report(extraction: dict) -> dict:
    checks: list[dict] = []
    empirical = [
        item
        for item in safe_list(extraction, "evidence_items")
        if isinstance(item, dict) and item.get("evidence_type") in EMPIRICAL_EVIDENCE_TYPES
    ]
    with_durable_output = 0
    for item in empirical:
        has_artifact = bool(item.get("associated_artifacts"))
        has_results = bool(item.get("results"))
        has_spans = bool(item.get("text_spans"))
        ok = has_artifact or has_results or has_spans
        with_durable_output += int(ok)
        if not ok:
            checks.append(
                {
                    "name": "empirical_evidence_without_durable_output",
                    "status": "warn",
                    "object_id": item.get("id"),
                    "reason": "Empirical evidence should have an associated Artifact, structured Result, or TextSpan.",
                    "suggested_fix": "Attach a figure/table/report artifact, add structured result fields, or ground the evidence with a TextSpan.",
                }
            )
    score = 1.0 if not empirical else round(with_durable_output / len(empirical), 3)
    return {
        "empirical_evidence_items": len(empirical),
        "with_durable_output": with_durable_output,
        "score": score,
        "checks": checks,
    }


def safe_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def literature_quality_report(openalex_work: dict | None, analysis_year: int) -> dict:
    if not isinstance(openalex_work, dict):
        return {
            "source": "none",
            "available": False,
            "summary": "No OpenAlex work metadata supplied.",
            "metrics": {},
            "signals": [],
        }
    publication_year = openalex_work.get("publication_year")
    if not isinstance(publication_year, int):
        publication_year = None
    cited_by_count = openalex_work.get("cited_by_count")
    if not isinstance(cited_by_count, int):
        cited_by_count = None
    age_years = max(1, analysis_year - publication_year + 1) if publication_year else None
    citations_per_year = round(cited_by_count / age_years, 3) if cited_by_count is not None and age_years else None
    fwci = safe_float(openalex_work.get("fwci"))
    counts_by_year = openalex_work.get("counts_by_year") if isinstance(openalex_work.get("counts_by_year"), list) else []
    recent_citations = sum(
        item.get("cited_by_count", 0)
        for item in counts_by_year
        if isinstance(item, dict)
        and isinstance(item.get("year"), int)
        and item["year"] >= analysis_year - 2
        and isinstance(item.get("cited_by_count"), int)
    )
    signals: list[dict] = []
    is_retracted = bool(openalex_work.get("is_retracted"))
    signals.append(
        {
            "name": "retraction_status",
            "status": "fail" if is_retracted else "pass",
            "reason": "OpenAlex marks the work as retracted." if is_retracted else "OpenAlex does not mark the work as retracted.",
        }
    )
    if citations_per_year is None:
        citation_status = "unknown"
    elif citations_per_year >= 20:
        citation_status = "high"
    elif citations_per_year >= 5:
        citation_status = "moderate"
    elif citations_per_year >= 1:
        citation_status = "low"
    else:
        citation_status = "very_low"
    signals.append(
        {
            "name": "age_normalized_citation_rate",
            "status": citation_status,
            "reason": "Citations per publication-year; interpret as reach/context, not truth.",
        }
    )
    if fwci is not None:
        signals.append(
            {
                "name": "field_weighted_citation_impact",
                "status": "above_field_average" if fwci >= 1 else "below_field_average",
                "reason": "OpenAlex FWCI compares citations to expected citations for field/year/type when available.",
            }
        )
    summary = (
        f"{cited_by_count if cited_by_count is not None else 'unknown'} citations over "
        f"{age_years if age_years is not None else 'unknown'} publication-year(s)"
    )
    return {
        "source": "openalex",
        "available": True,
        "summary": summary,
        "metrics": {
            "openalex_id": openalex_work.get("id"),
            "doi": openalex_work.get("doi"),
            "display_name": openalex_work.get("display_name"),
            "publication_year": publication_year,
            "analysis_year": analysis_year,
            "age_years": age_years,
            "cited_by_count": cited_by_count,
            "citations_per_year": citations_per_year,
            "recent_3yr_citations": recent_citations,
            "fwci": fwci,
            "is_retracted": is_retracted,
            "type": openalex_work.get("type"),
        },
        "signals": signals,
        "caveat": "Citation metrics are source-quality context only; they do not establish whether the paper's claims are correct.",
    }


def conversion_quality_report(report_parts: dict) -> dict:
    completeness_score = report_parts["completeness"].get("score", 0)
    density_score = report_parts["density"].get("score", 0)
    field_score = report_parts["field_quality"].get("overall_field_completeness_score", 0)
    artifact_score = report_parts["artifact_discipline"].get("score", 1)
    coverage = report_parts["coverage"]
    assertion_total = max(1, coverage.get("assertions", 0))
    evidence_linkage_score = coverage.get("with_evidence_links", 0) / assertion_total
    grounding = report_parts["grounding"]
    assertion_grounding = grounding["assertions"]["with_text_spans"] / max(1, sum(grounding["assertions"].values()))
    evidence_grounding = grounding["evidence_items"]["with_text_spans"] / max(1, sum(grounding["evidence_items"].values()))
    grounding_score = (assertion_grounding + evidence_grounding) / 2
    structural_issue_count = sum(report_parts["structural_issues"].values()) + coverage.get("assertions_missing_context", 0)
    structural_score = 1.0 if structural_issue_count == 0 else 0.0
    score = (
        structural_score * 0.20
        + grounding_score * 0.20
        + evidence_linkage_score * 0.20
        + density_score * 0.15
        + field_score * 0.15
        + artifact_score * 0.10
    )
    if score >= 0.9:
        band = "excellent"
    elif score >= 0.75:
        band = "good"
    elif score >= 0.5:
        band = "fair"
    else:
        band = "poor"
    return {
        "overall_conversion_score": round(score, 3),
        "band": band,
        "subscores": {
            "structural_integrity": round(structural_score, 3),
            "grounding": round(grounding_score, 3),
            "evidence_linkage": round(evidence_linkage_score, 3),
            "density": density_score,
            "field_quality": field_score,
            "artifact_discipline": artifact_score,
        },
        "interpretation": "Measures conversion/extraction quality, not whether the source literature itself is scientifically correct.",
    }


def collect_context_ids_from_extraction(extraction: dict) -> set[str]:
    context_ids: set[str] = set()

    def walk(value: Any) -> None:
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


def resolve_document_scope(document_scope: str, total_words: int, counts: dict) -> str:
    if document_scope != "auto":
        return document_scope
    if counts.get("assertions", 0) <= 2 or (total_words and total_words < 1500):
        return "lite"
    return "full_article"


def density_report(extraction: dict, counts: dict, coverage: dict, signals: dict, word_counts: dict[str, int], document_scope: str) -> dict:
    total_words = sum(word_counts.values())
    resolved_scope = resolve_document_scope(document_scope, total_words, counts)
    context_count = len(collect_context_ids_from_extraction(extraction))
    assertions = safe_list(extraction, "assertions")
    links = safe_list(extraction, "evidence_links")
    links_by_assertion: dict[str, list[dict]] = {}
    for link in links:
        if isinstance(link, dict) and isinstance(link.get("assertion"), str):
            links_by_assertion.setdefault(link["assertion"], []).append(link)

    checks: list[dict] = []

    def add(name: str, observed: int, target: int, *, strict_failure: bool = True, reason: str, suggested_fix: str) -> None:
        status = "pass" if observed >= target else "warn"
        checks.append({"name": name, "status": status, "observed": observed, "target": target, "strict_failure": strict_failure, "reason": reason, "suggested_fix": suggested_fix})

    if resolved_scope == "lite":
        add("lite_assertions", counts["assertions"], 1, strict_failure=False, reason="Lite artifacts need at least one assertion.", suggested_fix="Add one central Assertion.")
        add("lite_evidence_links", counts["evidence_links"], 1, strict_failure=False, reason="Lite artifacts need at least one evidence link.", suggested_fix="Link one EvidenceItem to one Assertion.")
        add("lite_contexts", context_count, 1, strict_failure=False, reason="Lite artifacts need at least one Context.", suggested_fix="Attach a Context to the Assertion.")
    elif resolved_scope == "short_note":
        add("short_note_assertions", counts["assertions"], 2, reason="Short notes should capture at least two claims when present.", suggested_fix="Extract at least two central assertions or justify absence in notes.")
        add("short_note_evidence_links", counts["evidence_links"], 2, reason="Short notes should include at least two evidence links.", suggested_fix="Link evidence for each central assertion.")
        add("short_note_contexts", context_count, 1, reason="Short notes need contextual scoping.", suggested_fix="Attach Context objects to assertions.")
    elif resolved_scope == "full_article":
        add("full_article_assertions", counts["assertions"], 5, reason="Full research articles require richer extraction density than a toy/demo.", suggested_fix="Extract objective, methods/results, conclusion, limitation, and other central claims.")
        add("full_article_contexts", context_count, 2, reason="Full articles should include multiple contexts when claims span methods/results/discussion.", suggested_fix="Add distinct Context objects for major claim scopes.")
        core_major = [a for a in assertions if a.get("criticality") in {"core", "major"}]
        with_link = sum(1 for a in core_major if links_by_assertion.get(a.get("id")))
        add("full_article_core_major_claims_with_evidence", with_link, len(core_major), strict_failure=False, reason="Every core/major claim should have at least one evidence link.", suggested_fix="Add EvidenceLinks for each core/major assertion.")
        core = [a for a in assertions if a.get("criticality") == "core"]
        core_with_two = sum(1 for a in core if len(links_by_assertion.get(a.get("id"), [])) >= 2)
        add("full_article_core_claims_with_two_evidence_links", core_with_two, len(core), strict_failure=False, reason="Core claims target at least two evidence links when source supports it.", suggested_fix="Add a second independent EvidenceLink for core assertions when possible.")
    elif resolved_scope == "benchmark_key":
        add("benchmark_assertions", counts["assertions"], 1, reason="Benchmark keys must include answer-key assertions.", suggested_fix="Add all answer-key assertions.")
        decisive = sum(1 for link in links if link.get("polarity") in {"supports", "refutes", "mixed"})
        add("benchmark_decisive_evidence_links", decisive, 1, reason="Benchmark keys need decisive evidence for answer claims.", suggested_fix="Add supports/refutes/mixed EvidenceLinks for answer-key claims.")
        add("benchmark_contexts", context_count, counts["assertions"], reason="Benchmark assertions should be scoped with Contexts.", suggested_fix="Attach Context objects to every answer-key assertion.")

    if resolved_scope != "lite":
        add("artifacts_from_captions", counts["artifacts"], 1 if signals["figure_or_table_caption_present"] else 0, reason="Figure/table captions should be represented as artifacts.", suggested_fix="Add Artifact objects for detected figures/tables.")
        add("datasets_from_availability_signals", counts["datasets"], 1 if signals["dataset_signal_present"] else 0, reason="Data-availability/accession signals should be represented as datasets.", suggested_fix="Add Dataset objects for source repository/accession signals.")

    passed = sum(1 for item in checks if item["status"] == "pass")
    return {"document_scope": resolved_scope, "requested_document_scope": document_scope, "source_word_count": total_words, "context_count": context_count, "score": round(passed / len(checks), 3) if checks else 1.0, "checks": checks}


def build_report(
    extraction: dict,
    source_markdown: str | None,
    article_json: dict | None = None,
    document_scope: str = "auto",
    openalex_work: dict | None = None,
    analysis_year: int | None = None,
) -> dict:
    assertions = safe_list(extraction, "assertions")
    evidence_items = safe_list(extraction, "evidence_items")
    evidence_links = safe_list(extraction, "evidence_links")
    analysis_year = analysis_year or date.today().year

    counts = {
        "artifacts": len(safe_list(extraction, "artifacts")),
        "datasets": len(safe_list(extraction, "datasets")),
        "entities": len(safe_list(extraction, "entities")),
        "studies": len(safe_list(extraction, "studies")),
        "experiments": sum(
            len(study.get("experiments", []) or [])
            for study in safe_list(extraction, "studies")
            if isinstance(study, dict)
        ),
        "assertions": len(assertions),
        "evidence_items": len(evidence_items),
        "evidence_links": len(evidence_links),
        "inferences": len(safe_list(extraction, "inferences")),
        "assertion_relations": len(safe_list(extraction, "assertion_relations")),
        "critiques": len(safe_list(extraction, "critiques")),
        "knowledge_gaps": len(safe_list(extraction, "knowledge_gaps")),
        "qa_items": len(safe_list(extraction, "qa_items")),
        "research_states": len(safe_list(extraction, "research_states")),
        "next_actions": len(safe_list(extraction, "next_actions")),
        "executions": len(safe_list(extraction, "executions")),
    }

    distributions = {
        "claim_role": value_distribution(assertions, "claim_role", CLAIM_ROLES),
        "criticality": value_distribution(assertions, "criticality", ASSERTION_CRITICALITIES),
        "normalization_status": value_distribution(assertions, "normalization_status", NORMALIZATION_STATUSES),
        "evidence_polarity": value_distribution(evidence_links, "polarity", POLARITIES),
        "evidence_strength": value_distribution(evidence_links, "strength", STRENGTHS),
        "research_state": value_distribution(safe_list(extraction, "research_states"), "state", RESEARCH_STATES),
    }

    grounding = {
        "assertions": text_span_coverage(assertions),
        "evidence_items": text_span_coverage(evidence_items),
        "evidence_links": text_span_coverage(evidence_links),
        "text_spans_by_section": text_span_section_distribution(extraction),
    }

    coverage = {
        **assertion_evidence_coverage(extraction),
        **context_coverage(extraction),
        "assertions_with_falsification_criteria": assertions_with_falsification(extraction),
    }

    structural = evidence_link_orphans(extraction)

    word_counts = count_words_per_section(source_markdown) if source_markdown else {}
    signals = article_signals(article_json, source_markdown)
    completeness = completeness_report(extraction, counts, coverage, signals, word_counts, document_scope)
    density = density_report(extraction, counts, coverage, signals, word_counts, document_scope)
    field_quality = field_quality_report(extraction)
    claim_readouts = build_claim_readouts(extraction)
    artifact_discipline = artifact_discipline_report(extraction)
    literature_quality = literature_quality_report(openalex_work, analysis_year)
    missing_or_weak = [
        {
            "category": item["name"],
            "severity": "error" if item["status"] == "fail" else "warning",
            "reason": item["reason"],
            "observed": item["observed"],
            "target": item["target"],
            "suggested_fix": item["suggested_fix"],
        }
        for item in completeness["checks"]
        if item["status"] != "pass"
    ]
    missing_or_weak.extend(
        {
            "category": "extraction_density",
            "severity": "error" if item["status"] == "fail" else "warning",
            "reason": item["reason"],
            "observed": item["observed"],
            "target": item["target"],
            "suggested_fix": item["suggested_fix"],
        }
        for item in density["checks"]
        if item["status"] != "pass"
    )
    missing_or_weak.extend(
        {
            "category": "artifact_discipline",
            "severity": "warning",
            "object_id": item.get("object_id"),
            "reason": item["reason"],
            "suggested_fix": item["suggested_fix"],
        }
        for item in artifact_discipline["checks"]
        if item["status"] != "pass"
    )
    for collection, info in field_quality["collections"].items():
        for item in info["objects_with_missing_required"]:
            missing_or_weak.append(
                {
                    "category": "field_quality",
                    "severity": "error",
                    "object_id": item["id"],
                    "field": collection,
                    "reason": f"missing required fields: {', '.join(item['missing_required'])}",
                    "suggested_fix": "Populate required fields from the manuscript or remove unsupported objects.",
                }
            )
        if info["missing_recommended_by_field"]:
            missing_or_weak.append(
                {
                    "category": "field_quality",
                    "severity": "warning",
                    "field": collection,
                    "reason": f"missing recommended fields: {dict(info['missing_recommended_by_field'])}",
                    "suggested_fix": "Improve grounding, criticality, rationale, and provenance fields where the manuscript supports them.",
                }
            )

    issues: list[str] = []
    if coverage["assertions_missing_context"]:
        issues.append(
            f"{coverage['assertions_missing_context']} assertion(s) missing required Context"
        )
    if structural["evidence_links_with_unknown_assertion"]:
        issues.append(
            f"{structural['evidence_links_with_unknown_assertion']} evidence_link(s) point to unknown assertion ids"
        )
    if structural["evidence_links_with_unknown_evidence_item"]:
        issues.append(
            f"{structural['evidence_links_with_unknown_evidence_item']} evidence_link(s) point to unknown evidence_item ids"
        )
    if literature_quality.get("available"):
        for signal in literature_quality.get("signals", []):
            if signal.get("status") == "fail":
                issues.append(f"literature_quality: {signal.get('reason')}")
    for item in missing_or_weak:
        if item["severity"] == "error":
            issues.append(
                f"{item['category']}: {item['reason']} (suggested fix: {item['suggested_fix']})"
            )

    conversion_parts = {
        "completeness": completeness,
        "density": density,
        "field_quality": field_quality,
        "artifact_discipline": artifact_discipline,
        "coverage": coverage,
        "grounding": grounding,
        "structural_issues": structural,
    }
    conversion_quality = conversion_quality_report(conversion_parts)

    return {
        "extraction_id": extraction.get("id"),
        "title": extraction.get("title"),
        "doi": extraction.get("doi"),
        "pmid": extraction.get("pmid"),
        "counts": counts,
        "distributions": distributions,
        "grounding": grounding,
        "coverage": coverage,
        "completeness": completeness,
        "density": density,
        "conversion_quality": conversion_quality,
        "claim_readouts": claim_readouts,
        "artifact_discipline": artifact_discipline,
        "literature_quality": literature_quality,
        "missing_or_weak": missing_or_weak,
        "field_quality": field_quality,
        "source_signals": signals,
        "structural_issues": structural,
        "section_word_counts": word_counts,
        "issues": issues,
    }


def render_text(report: dict) -> str:
    lines: list[str] = []
    lines.append("CSAG quality report")
    lines.append(f"  id:    {report.get('extraction_id')}")
    lines.append(f"  title: {report.get('title')}")
    lines.append(f"  doi:   {report.get('doi')}")
    lines.append(f"  pmid:  {report.get('pmid')}")
    lines.append("")
    lines.append("Counts:")
    for key, value in report["counts"].items():
        lines.append(f"  {key:<22} {value}")
    lines.append("")
    lines.append("Coverage:")
    for key, value in report["coverage"].items():
        lines.append(f"  {key:<40} {value}")
    lines.append("")
    lines.append("Completeness:")
    completeness = report.get("completeness", {})
    lines.append(f"  document_scope: {completeness.get('document_scope')}")
    lines.append(f"  score:          {completeness.get('score')}")
    for item in completeness.get("checks", []):
        status = item.get("status", "unknown")
        lines.append(
            f"  {item.get('name', ''):<36} {status:<5} "
            f"{item.get('observed')}/{item.get('target')}"
        )
    lines.append("")
    lines.append("Extraction density:")
    density = report.get("density", {})
    lines.append(f"  document_scope: {density.get('document_scope')}")
    lines.append(f"  score:          {density.get('score')}")
    for item in density.get("checks", []):
        status = item.get("status", "unknown")
        lines.append(
            f"  {item.get('name', ''):<42} {status:<5} "
            f"{item.get('observed')}/{item.get('target')}"
        )
    lines.append("")
    conversion = report.get("conversion_quality", {})
    lines.append("Conversion quality:")
    lines.append(f"  overall_conversion_score: {conversion.get('overall_conversion_score')}")
    lines.append(f"  band:                     {conversion.get('band')}")
    for name, value in conversion.get("subscores", {}).items():
        lines.append(f"  {name:<26} {value}")
    lines.append("")
    claim_readouts = report.get("claim_readouts", [])
    lines.append("Claim readouts:")
    if claim_readouts:
        for item in claim_readouts[:10]:
            lines.append(f"  - {item.get('assertion_id')}: {item.get('state')} | {item.get('assertion_text')}")
            lines.append(f"    current_read: {item.get('current_read')}")
            lines.append(
                "    evidence: "
                f"for={len(item.get('evidence_for', []))}, "
                f"against={len(item.get('evidence_against', []))}, "
                f"mixed/inconclusive={len(item.get('mixed_or_inconclusive', []))}, "
                f"next_actions={len(item.get('next_actions', []))}"
            )
    else:
        lines.append("  (none)")
    lines.append("")
    artifact_discipline = report.get("artifact_discipline", {})
    lines.append("Artifact discipline:")
    lines.append(f"  empirical_evidence_items: {artifact_discipline.get('empirical_evidence_items')}")
    lines.append(f"  with_durable_output:      {artifact_discipline.get('with_durable_output')}")
    lines.append(f"  score:                    {artifact_discipline.get('score')}")
    lines.append("")
    literature_quality = report.get("literature_quality", {})
    lines.append("Literature quality:")
    lines.append(f"  source:  {literature_quality.get('source')}")
    lines.append(f"  summary: {literature_quality.get('summary')}")
    for signal in literature_quality.get("signals", []):
        lines.append(f"  {signal.get('name'):<34} {signal.get('status')}")
    lines.append("")
    lines.append("Field quality:")
    field_quality = report.get("field_quality", {})
    lines.append(f"  overall_field_completeness_score: {field_quality.get('overall_field_completeness_score')}")
    lines.append(f"  missing_required_field_count:     {field_quality.get('missing_required_field_count')}")
    lines.append(f"  missing_recommended_field_count:  {field_quality.get('missing_recommended_field_count')}")
    for name, info in field_quality.get("collections", {}).items():
        if info.get("object_count"):
            lines.append(
                f"  {name:<22} score={info.get('field_completeness_score')} "
                f"objects={info.get('object_count')}"
            )
    lines.append("")
    if report.get("missing_or_weak"):
        lines.append("Missing or weak coverage:")
        for item in report["missing_or_weak"]:
            subject = item.get("object_id") or item.get("field") or item.get("category")
            lines.append(f"  - [{item.get('severity')}] {subject}: {item.get('reason')}")
        lines.append("")
    lines.append("Distributions:")
    for name, distribution in report["distributions"].items():
        active = {k: v for k, v in distribution.items() if v}
        rendered = ", ".join(f"{k}={v}" for k, v in active.items()) or "(empty)"
        lines.append(f"  {name:<22} {rendered}")
    lines.append("")
    lines.append("Grounding:")
    for category, info in report["grounding"].items():
        lines.append(f"  {category}: {info}")
    lines.append("")
    if report["section_word_counts"]:
        lines.append("Section word counts (from --source-markdown):")
        for section, count in sorted(report["section_word_counts"].items(), key=lambda item: -item[1]):
            lines.append(f"  {section:<40} {count}")
        lines.append("")
    if report["issues"]:
        lines.append("Issues:")
        for issue in report["issues"]:
            lines.append(f"  - {issue}")
    else:
        lines.append("Issues: none detected")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    extraction_path = args.extraction_json.expanduser().resolve()
    report_path = args.report_out.expanduser().resolve() if args.report_out else None
    base_dir = report_path.parent if report_path else extraction_path.parent
    source_path = args.source_markdown.expanduser().resolve() if args.source_markdown else None
    article_path = args.article_json.expanduser().resolve() if args.article_json else None
    openalex_path = args.openalex_json.expanduser().resolve() if args.openalex_json else None
    extraction = json.loads(extraction_path.read_text(encoding="utf-8"))
    if not isinstance(extraction, dict):
        print("ERROR: extraction JSON is not an object", file=sys.stderr)
        return 2

    markdown = None
    if args.source_markdown:
        markdown = args.source_markdown.expanduser().resolve().read_text(encoding="utf-8")

    article_json = None
    if args.article_json:
        article_json = json.loads(args.article_json.expanduser().resolve().read_text(encoding="utf-8"))

    openalex_work = None
    if args.openalex_json:
        openalex_work = json.loads(args.openalex_json.expanduser().resolve().read_text(encoding="utf-8"))

    report = build_report(extraction, markdown, article_json, args.document_scope, openalex_work, args.analysis_year)
    report["inputs"] = input_records(
        base_dir=base_dir,
        extraction=extraction_path,
        source_markdown=source_path,
        article_json=article_path,
        openalex_json=openalex_path,
    )
    if args.strict:
        for item in report.get("density", {}).get("checks", []):
            if item.get("status") != "pass" and item.get("strict_failure", True):
                report["issues"].append(
                    f"extraction_density: {item.get('reason')} (suggested fix: {item.get('suggested_fix')})"
                )
    print(render_text(report))

    if args.report_out:
        out_path = report_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nreport={out_path}")

    if args.strict and report["issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
