from __future__ import annotations

from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import unicodedata
from typing import Hashable

from .paths import CommandResult
from .provenance import input_records
from .validate import validate_extraction


SCORER_VERSION = "csag-score/2"
WEIGHT_KEYS = ("assertion_text", "evidence_polarity", "context", "grounding")
PARTIAL_CREDIT_KEYS = (
    "missing_evidence",
    "unsupported_claim",
    "wrong_polarity",
    "missing_context",
    "missing_grounding",
    "hallucinated_assertions",
)
CONTEXT_METADATA = {
    "id",
    "text_spans",
    "provenance",
    "origin",
    "curation_status",
    "confidence_score",
    "created_on",
    "created_by",
    "generated_by",
    "derived_from",
}


def _normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(text.casefold().split())


def _clean_semantic(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _clean_semantic(nested)
            for key, nested in sorted(value.items())
            if key not in CONTEXT_METADATA and nested not in (None, "", [], {})
        }
    if isinstance(value, list):
        cleaned = [_clean_semantic(item) for item in value]
        return sorted(cleaned, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, str):
        return _normalize_text(value)
    return value


def _context_signatures(assertion: dict) -> set[str]:
    return {
        json.dumps(_clean_semantic(context), sort_keys=True, separators=(",", ":"))
        for context in assertion.get("contexts", []) or []
        if isinstance(context, dict)
    }


def _span_signatures(item: dict) -> set[tuple[object, ...]]:
    return {
        (
            _normalize_text(span.get("document_id")),
            _normalize_text(span.get("section_type")),
            span.get("start_char"),
            span.get("end_char"),
            _normalize_text(span.get("exact_text")),
        )
        for span in item.get("text_spans", []) or []
        if isinstance(span, dict)
    }


def _set_f1(expected: set[Hashable], observed: set[Hashable]) -> float:
    if not expected and not observed:
        return 1.0
    if not expected or not observed:
        return 0.0
    matched = len(expected & observed)
    precision = matched / len(observed)
    recall = matched / len(expected)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _counter_f1(expected: Counter, observed: Counter) -> float:
    expected_total = sum(expected.values())
    observed_total = sum(observed.values())
    if not expected_total and not observed_total:
        return 1.0
    if not expected_total or not observed_total:
        return 0.0
    matched = sum((expected & observed).values())
    precision = matched / observed_total
    recall = matched / expected_total
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _evidence_signatures(extraction: dict, assertion_id: str) -> Counter:
    evidence_by_id = {
        item["id"]: item
        for item in extraction.get("evidence_items", []) or []
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    signatures: Counter = Counter()
    for link in extraction.get("evidence_links", []) or []:
        if not isinstance(link, dict) or link.get("assertion") != assertion_id:
            continue
        evidence = evidence_by_id.get(link.get("evidence_item"))
        if not evidence:
            continue
        spans = tuple(sorted(_span_signatures(evidence)))
        basis = (
            "content",
            _normalize_text(evidence.get("evidence_text")),
            spans,
        )
        signatures[(_normalize_text(link.get("polarity")), basis)] += 1
    return signatures


def _validate_scoring_schema(scoring_schema: dict, answer_key: dict) -> tuple[list[str], dict[str, tuple[str, str]]]:
    errors: list[str] = []

    def nonnegative_finite_number(value: object) -> bool:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        try:
            return math.isfinite(value) and value >= 0
        except (OverflowError, TypeError, ValueError):
            return False

    weights = scoring_schema.get("weights")
    if not isinstance(weights, dict):
        errors.append("scoring_schema.weights must be an object")
    else:
        for key in WEIGHT_KEYS:
            value = weights.get(key)
            if not nonnegative_finite_number(value):
                errors.append(
                    f"scoring_schema.weights.{key} must be a non-negative finite number"
                )
        if all(nonnegative_finite_number(weights.get(key)) for key in WEIGHT_KEYS):
            if abs(sum(float(weights[key]) for key in WEIGHT_KEYS) - 1.0) > 1e-9:
                errors.append("scoring_schema.weights must sum to 1.0")

    penalty = scoring_schema.get("false_positive_penalty")
    if not nonnegative_finite_number(penalty):
        errors.append(
            "scoring_schema.false_positive_penalty must be a non-negative finite number"
        )

    key_assertions = {
        assertion["id"]: assertion
        for assertion in answer_key.get("assertions", []) or []
        if isinstance(assertion, dict) and isinstance(assertion.get("id"), str)
    }
    forms: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for assertion_id, assertion in key_assertions.items():
        normalized = _normalize_text(assertion.get("assertion_text"))
        if normalized:
            forms[normalized].append((assertion_id, "canonical"))

    equivalents = scoring_schema.get("allowed_equivalent_formulations", [])
    if not isinstance(equivalents, list):
        errors.append("scoring_schema.allowed_equivalent_formulations must be a list")
    else:
        for index, item in enumerate(equivalents):
            if not isinstance(item, dict):
                errors.append(f"scoring_schema.allowed_equivalent_formulations[{index}] must be an object")
                continue
            assertion_id = item.get("assertion")
            equivalent_text = item.get("equivalent_text")
            if assertion_id not in key_assertions:
                errors.append(f"scoring_schema.allowed_equivalent_formulations[{index}].assertion must reference an answer-key assertion")
            if not isinstance(equivalent_text, str) or not equivalent_text.strip():
                errors.append(f"scoring_schema.allowed_equivalent_formulations[{index}].equivalent_text is required")
                continue
            if assertion_id in key_assertions:
                forms[_normalize_text(equivalent_text)].append((assertion_id, "equivalent"))

    form_index: dict[str, tuple[str, str]] = {}
    for normalized, targets in forms.items():
        assertion_ids = {target[0] for target in targets}
        if len(assertion_ids) > 1:
            errors.append(f"normalized assertion formulation is ambiguous across answer-key assertions: {normalized!r}")
            continue
        canonical = next((target for target in targets if target[1] == "canonical"), targets[0])
        form_index[normalized] = canonical

    partial_credit = scoring_schema.get("partial_credit")
    if not isinstance(partial_credit, dict):
        errors.append("scoring_schema.partial_credit must be an object")
    else:
        for key in PARTIAL_CREDIT_KEYS:
            if not isinstance(partial_credit.get(key), str) or not partial_credit[key].strip():
                errors.append(f"scoring_schema.partial_credit.{key} is required")
    if not isinstance(scoring_schema.get("expert_disagreement_note"), str) or not scoring_schema["expert_disagreement_note"].strip():
        errors.append("scoring_schema.expert_disagreement_note is required")
    return errors, form_index


def _pair_score(
    key_extraction: dict,
    participant: dict,
    key_assertion: dict,
    participant_assertion: dict,
    weights: dict[str, float],
) -> dict:
    context_f1 = _set_f1(_context_signatures(key_assertion), _context_signatures(participant_assertion))
    grounding_f1 = _set_f1(_span_signatures(key_assertion), _span_signatures(participant_assertion))
    evidence_f1 = _counter_f1(
        _evidence_signatures(key_extraction, key_assertion["id"]),
        _evidence_signatures(participant, participant_assertion["id"]),
    )
    components = {
        "assertion_text": 1.0,
        "evidence_polarity": evidence_f1,
        "context": context_f1,
        "grounding": grounding_f1,
    }
    weighted = {key: components[key] * weights[key] for key in WEIGHT_KEYS}
    return {
        "component_scores": {key: round(value, 6) for key, value in components.items()},
        "weighted_components": {key: round(value, 6) for key, value in weighted.items()},
        "score": sum(weighted.values()),
    }


def _failure(
    report_out: Path,
    errors: list[str],
    answer_key: Path,
    participant: Path,
    scoring_schema: Path,
) -> CommandResult:
    available_inputs = {
        name: path
        for name, path in {
            "answer_key": answer_key,
            "participant": participant,
            "scoring_schema": scoring_schema,
        }.items()
        if path.is_file()
    }
    payload = {
        "ok": False,
        "scorer_version": SCORER_VERSION,
        "errors": errors,
        "inputs": input_records(base_dir=report_out.parent, **available_inputs),
    }
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    stderr = "".join(f"ERROR: {error}\n" for error in errors)
    return CommandResult(False, 1, report_out, payload, stderr=stderr)


def score_extraction(*, answer_key: Path, participant: Path, scoring_schema: Path, report_out: Path) -> CommandResult:
    answer_key = answer_key.expanduser().resolve()
    participant = participant.expanduser().resolve()
    scoring_schema = scoring_schema.expanduser().resolve()
    report_out = report_out.expanduser().resolve()

    payloads: dict[str, dict] = {}
    load_errors: list[str] = []
    for label, path in (
        ("answer key", answer_key),
        ("participant", participant),
        ("scoring schema", scoring_schema),
    ):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            detail = exc.strerror or exc.__class__.__name__
            load_errors.append(f"{label}: cannot read input ({detail})")
            continue
        except json.JSONDecodeError as exc:
            load_errors.append(
                f"{label}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
            )
            continue
        if not isinstance(payload, dict):
            load_errors.append(f"{label}: root value must be a JSON object")
            continue
        payloads[label] = payload
    if load_errors:
        return _failure(
            report_out,
            load_errors,
            answer_key,
            participant,
            scoring_schema,
        )

    key_validation = validate_extraction(answer_key, profile="benchmark_key")
    participant_validation = validate_extraction(participant, profile="paper_local")
    validation_errors: list[str] = []
    if not key_validation.ok:
        validation_errors.extend(f"answer key: {error}" for error in (key_validation.data or {}).get("errors", []))
    if not participant_validation.ok:
        validation_errors.extend(f"participant: {error}" for error in (participant_validation.data or {}).get("errors", []))
    if validation_errors:
        return _failure(report_out, validation_errors, answer_key, participant, scoring_schema)

    key_payload = payloads["answer key"]
    participant_payload = payloads["participant"]
    schema_payload = payloads["scoring schema"]
    errors, form_index = _validate_scoring_schema(schema_payload, key_payload)
    if key_payload.get("id") != participant_payload.get("id"):
        errors.append("answer key and participant must identify the same manuscript")
    if errors:
        return _failure(report_out, errors, answer_key, participant, scoring_schema)

    weights = {key: float(schema_payload["weights"][key]) for key in WEIGHT_KEYS}
    candidates: dict[str, list[tuple[dict, str]]] = defaultdict(list)
    unmatched: list[dict] = []
    for assertion in participant_payload.get("assertions", []) or []:
        target = form_index.get(_normalize_text(assertion.get("assertion_text")))
        if target:
            candidates[target[0]].append((assertion, target[1]))
        else:
            unmatched.append(assertion)

    rows: list[dict] = []
    total = 0.0
    possible = float(len(key_payload.get("assertions", []) or []))
    for key_assertion in key_payload.get("assertions", []) or []:
        assertion_id = key_assertion["id"]
        scored_candidates: list[tuple[float, str, dict, str, dict]] = []
        for assertion, match_basis in candidates.get(assertion_id, []):
            pair = _pair_score(key_payload, participant_payload, key_assertion, assertion, weights)
            scored_candidates.append((pair["score"], assertion["id"], assertion, match_basis, pair))
        scored_candidates.sort(key=lambda item: (-item[0], item[1]))
        if not scored_candidates:
            rows.append(
                {
                    "assertion": assertion_id,
                    "participant_assertion": None,
                    "match_basis": None,
                    "component_scores": {key: 0.0 for key in WEIGHT_KEYS},
                    "weighted_components": {key: 0.0 for key in WEIGHT_KEYS},
                    "score": 0.0,
                    "possible": 1.0,
                    "reasons": ["assertion missing"],
                }
            )
            continue
        _, _, chosen, match_basis, pair = scored_candidates[0]
        unmatched.extend(item[2] for item in scored_candidates[1:])
        reasons = [
            f"{key} partial or missing"
            for key, value in pair["component_scores"].items()
            if value < 1.0
        ]
        score = round(pair["score"], 6)
        total += score
        rows.append(
            {
                "assertion": assertion_id,
                "participant_assertion": chosen["id"],
                "match_basis": match_basis,
                "component_scores": pair["component_scores"],
                "weighted_components": pair["weighted_components"],
                "score": score,
                "possible": 1.0,
                "reasons": reasons,
            }
        )

    false_positive_ids = [assertion["id"] for assertion in unmatched]
    penalty = float(schema_payload["false_positive_penalty"]) * len(false_positive_ids)
    final_score = max(0.0, total - penalty)
    payload = {
        "ok": True,
        "scorer_version": SCORER_VERSION,
        "inputs": input_records(
            base_dir=report_out.parent,
            answer_key=answer_key,
            participant=participant,
            scoring_schema=scoring_schema,
        ),
        "score": round(final_score, 6),
        "possible": round(possible, 6),
        "normalized_score": round(final_score / possible, 6) if possible else 0.0,
        "false_positive_assertions": false_positive_ids,
        "false_positive_penalty": round(penalty, 6),
        "assertion_scores": rows,
        "expert_disagreement_note": schema_payload["expert_disagreement_note"],
    }
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return CommandResult(True, 0, report_out, payload)
