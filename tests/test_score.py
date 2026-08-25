from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

import csag.cli as cli
from csag.paths import ROOT
from csag.provenance import check_report_inputs
from csag.score import score_extraction


FIXTURES = ROOT / "tests/fixtures/benchmark"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def score(tmp_path: Path, participant: dict, schema: dict | None = None):
    participant_path = write(tmp_path / "participant.json", participant)
    schema_path = write(tmp_path / "scoring_schema.json", schema or load("scoring_schema.json"))
    report_path = tmp_path / "score.json"
    result = score_extraction(
        answer_key=FIXTURES / "answer_key.hidden.json",
        participant=participant_path,
        scoring_schema=schema_path,
        report_out=report_path,
    )
    return result, json.loads(report_path.read_text(encoding="utf-8"))


def rename_local_ids(payload: dict) -> dict:
    renamed = deepcopy(payload)
    document_id = renamed["id"]
    mapping: dict[str, str] = {}
    counter = 0

    def collect(value: object) -> None:
        nonlocal counter
        if isinstance(value, dict):
            item_id = value.get("id")
            if isinstance(item_id, str) and item_id != document_id:
                counter += 1
                mapping[item_id] = f"urn:participant:{counter:04d}"
            for nested in value.values():
                collect(nested)
        elif isinstance(value, list):
            for nested in value:
                collect(nested)

    def replace(value: object) -> object:
        if isinstance(value, dict):
            return {key: replace(nested) for key, nested in value.items()}
        if isinstance(value, list):
            return [replace(nested) for nested in value]
        if isinstance(value, str):
            return mapping.get(value, value)
        return value

    collect(renamed)
    return replace(renamed)


def test_independent_local_ids_preserve_score(tmp_path: Path) -> None:
    participant = rename_local_ids(load("participant_output.json"))
    result, report = score(tmp_path, participant)
    assert result.ok
    assert report["normalized_score"] == 0.75
    assert all(row["participant_assertion"].startswith("urn:participant:") for row in report["assertion_scores"])
    assert all(not Path(record["path"]).is_absolute() for record in report["inputs"].values())
    assert all(record["size_bytes"] > 0 for record in report["inputs"].values())
    assert check_report_inputs(tmp_path / "score.json", report) == (True, [])


def test_dangling_evidence_stops_before_numeric_score(tmp_path: Path) -> None:
    participant = load("participant_output.json")
    participant["evidence_links"][0]["evidence_item"] = "urn:missing:evidence"
    result, report = score(tmp_path, participant)
    assert not result.ok
    assert "normalized_score" not in report
    assert any("does not resolve" in error for error in report["errors"])


def test_evidence_interpretation_must_match_even_with_copied_span(tmp_path: Path) -> None:
    participant = load("participant_output.json")
    participant["evidence_items"][0]["evidence_text"] = (
        "Blue light reduced pigment relative to the dark control."
    )
    result, report = score(tmp_path, participant)
    assert result.ok
    row = next(
        row for row in report["assertion_scores"] if row["assertion"].endswith("A0002")
    )
    assert row["component_scores"]["evidence_polarity"] == 0.0
    assert row["component_scores"]["context"] == 1.0
    assert row["component_scores"]["grounding"] == 1.0


@pytest.mark.parametrize(
    "value",
    [True, float("nan"), float("inf"), float("-inf"), 10**400],
)
def test_non_finite_or_boolean_weights_are_rejected(
    tmp_path: Path, value: object
) -> None:
    schema = load("scoring_schema.json")
    schema["weights"]["assertion_text"] = value
    result, report = score(tmp_path, load("participant_output.json"), schema)
    assert not result.ok
    assert "normalized_score" not in report
    assert any("non-negative finite number" in error for error in report["errors"])


@pytest.mark.parametrize(
    "value",
    [True, float("nan"), float("inf"), float("-inf"), 10**400],
)
def test_non_finite_or_boolean_false_positive_penalty_is_rejected(
    tmp_path: Path, value: object
) -> None:
    schema = load("scoring_schema.json")
    schema["false_positive_penalty"] = value
    result, report = score(tmp_path, load("participant_output.json"), schema)
    assert not result.ok
    assert "normalized_score" not in report
    assert any("non-negative finite number" in error for error in report["errors"])


def test_malformed_schema_writes_structured_failure_report(tmp_path: Path) -> None:
    schema_path = tmp_path / "malformed.json"
    schema_path.write_text("{not-json\n", encoding="utf-8")
    report_path = tmp_path / "score.json"
    code = cli.main(
        [
            "score",
            "--answer-key",
            str(FIXTURES / "answer_key.hidden.json"),
            "--participant",
            str(FIXTURES / "participant_output.json"),
            "--scoring-schema",
            str(schema_path),
            "--report-out",
            str(report_path),
        ]
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert code == 1
    assert report["ok"] is False
    assert "normalized_score" not in report
    assert any("scoring schema: invalid JSON" in error for error in report["errors"])
    assert check_report_inputs(report_path, report) == (True, [])


def test_missing_participant_writes_structured_failure_report(tmp_path: Path) -> None:
    report_path = tmp_path / "score.json"
    result = score_extraction(
        answer_key=FIXTURES / "answer_key.hidden.json",
        participant=tmp_path / "missing-participant.json",
        scoring_schema=FIXTURES / "scoring_schema.json",
        report_out=report_path,
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert not result.ok
    assert report["ok"] is False
    assert "participant" not in report["inputs"]
    assert any("participant: cannot read input" in error for error in report["errors"])


def test_key_ids_with_bogus_content_receive_only_text_credit(tmp_path: Path) -> None:
    participant = load("participant_output.json")
    participant["assertions"] = participant["assertions"][:2]
    for index, assertion in enumerate(participant["assertions"], start=1):
        assertion["contexts"] = [
            {
                "id": f"urn:bogus:context:{index}",
                "label": "wrong context",
                "context_facet": "other",
            }
        ]
        assertion["text_spans"] = [
            {
                "id": f"urn:bogus:span:{index}",
                "document_id": participant["id"],
                "section_type": "other",
                "start_char": index,
                "end_char": index + 1,
                "exact_text": "x",
            }
        ]
    participant["evidence_items"][0]["evidence_text"] = "unrelated evidence"
    participant["evidence_items"][0]["text_spans"] = [
        {
            "id": "urn:bogus:evidence-span",
            "document_id": participant["id"],
            "section_type": "other",
            "start_char": 10,
            "end_char": 11,
            "exact_text": "y",
        }
    ]
    participant["evidence_links"][0]["polarity"] = "refutes"
    result, report = score(tmp_path, participant)
    assert result.ok
    assert report["normalized_score"] == 0.4
    for row in report["assertion_scores"]:
        assert row["component_scores"] == {
            "assertion_text": 1.0,
            "evidence_polarity": 0.0,
            "context": 0.0,
            "grounding": 0.0,
        }


def test_duplicate_candidate_matches_once_and_is_penalized(tmp_path: Path) -> None:
    participant = load("participant_output.json")
    duplicate = deepcopy(participant["assertions"][1])
    duplicate["id"] = "urn:duplicate:assertion"
    duplicate["contexts"][0]["id"] = "urn:duplicate:context"
    duplicate["text_spans"][0]["id"] = "urn:duplicate:span"
    participant["assertions"].append(duplicate)
    result, report = score(tmp_path, participant)
    assert result.ok
    assert "urn:duplicate:assertion" in report["false_positive_assertions"]
    matched = [row for row in report["assertion_scores"] if row["assertion"].endswith("A0002")]
    assert len(matched) == 1


def test_ambiguous_equivalent_formulation_is_rejected(tmp_path: Path) -> None:
    schema = load("scoring_schema.json")
    schema["allowed_equivalent_formulations"].append(
        {
            "assertion": "csag:assertion/csag:doc/toy_plastid_claim/A0001",
            "equivalent_text": "Blue light increases plastid pigment accumulation in the toy algal system.",
        }
    )
    result, report = score(tmp_path, load("participant_output.json"), schema)
    assert not result.ok
    assert any("ambiguous" in error for error in report["errors"])


@pytest.mark.parametrize(
    ("component", "mutate"),
    [
        ("evidence_polarity", lambda payload: payload["evidence_links"][0].update(polarity="refutes")),
        ("context", lambda payload: payload["assertions"][1]["contexts"][0].update(label="wrong context")),
        ("grounding", lambda payload: payload["assertions"][1]["text_spans"][0].update(start_char=574)),
    ],
)
def test_component_changes_are_isolated(tmp_path: Path, component: str, mutate) -> None:
    participant = load("participant_output.json")
    mutate(participant)
    result, report = score(tmp_path, participant)
    assert result.ok
    row = next(row for row in report["assertion_scores"] if row["assertion"].endswith("A0002"))
    assert row["component_scores"][component] < 1.0
    for other, value in row["component_scores"].items():
        if other != component:
            assert value == 1.0
