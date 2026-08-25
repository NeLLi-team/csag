"""Synthetic unit tests proving the v2 scorer is span-anchored and symmetric.

These tests prove the corrected, non-circular grounding contract:
  * a prose-style response (overlapping but not identical span) earns overlap
    credit (grounding_f1 > 0);
  * a csag-style response returning the exact gold span earns grounding_f1 == 1.0;
  * a legacy response returning a 'csag:evidence/...//E0001' style ID and NO
    spans earns grounding_f1 == 0 (IDs are NOT credited; only spans are) -- the
    echo-the-ID exploit is dead;
  * the scorer never reads any 'required_evidence_ids' / 'csag:' gold fields.

The scorer lives under scripts/ and is imported directly from there.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import score_eval_v2 as scorer  # noqa: E402


GOLD_DOC = "P"
GOLD_TASK = {
    "id": "T001",
    "task_type": "context_sensitive_qa",
    "answer": "deep-branching algal lineage",
    "gold_spans": [{"document_id": GOLD_DOC, "start": 100, "end": 200}],
}


def _row(parsed: dict, condition: str = "prose_rag") -> dict:
    return {
        "task_id": "T001",
        "task_name": "context_qa",
        "condition": condition,
        "model": "synthetic/model",
        "parsed_json": parsed,
    }


def test_prose_style_overlapping_span_earns_partial_credit() -> None:
    # Returned [120, 210) overlaps gold [100, 200): overlap=80 chars.
    # recall=80/100=0.8, precision=80/90=0.889 -> f1~=0.842. Partial (not full)
    # credit for an offset span is the correct, character-level behavior.
    parsed = {
        "answer": "deep-branching algal lineage",
        "returned_spans": [{"document_id": GOLD_DOC, "start": 120, "end": 210}],
    }
    result = scorer.score_row(_row(parsed, condition="prose_rag"), GOLD_TASK)
    assert result["grounding_f1"] > 0.0
    assert result["grounding_f1"] < 1.0  # offset span -> partial, not full
    assert result["grounding_recall"] == pytest.approx(0.8)
    assert result["grounding_precision"] == pytest.approx(80 / 90)
    assert result["grounding_f1"] == pytest.approx(2 * 0.8 * (80 / 90) / (0.8 + 80 / 90))


def test_whole_document_span_cannot_game_grounding() -> None:
    # THE anti-gaming guarantee. A single span swallowing the whole document
    # covers all gold (recall 1.0) but is almost all off-target, so precision
    # ~= gold_len/returned_len -> ~0 and F1 collapses. A lazy/adversarial model
    # cannot get grounding credit by returning one giant span.
    parsed = {"answer": "x", "returned_spans": [{"document_id": GOLD_DOC, "start": 0, "end": 5000}]}
    result = scorer.score_row(_row(parsed), GOLD_TASK)
    assert result["grounding_recall"] == 1.0
    assert result["grounding_precision"] == pytest.approx(100 / 5000)
    assert result["grounding_f1"] < 0.1

    # Same with multiple gold spans: still uncovered by a single giant span.
    multi_gold = {
        **GOLD_TASK,
        "gold_spans": [
            {"document_id": GOLD_DOC, "start": 100, "end": 200},
            {"document_id": GOLD_DOC, "start": 1000, "end": 1100},
        ],
    }
    result2 = scorer.score_row(_row(parsed), multi_gold)
    assert result2["grounding_recall"] == 1.0
    assert result2["grounding_f1"] < 0.1


def test_overlapping_returned_spans_counted_once() -> None:
    # Returned [100,200) and [150,250) merge to [100,250) (len 150); gold [100,200)
    # overlap 100 -> recall 1.0, precision 100/150. Character union prevents
    # double-counting overlapping returned spans.
    parsed = {
        "answer": "x",
        "returned_spans": [
            {"document_id": GOLD_DOC, "start": 100, "end": 200},
            {"document_id": GOLD_DOC, "start": 150, "end": 250},
        ],
    }
    result = scorer.score_row(_row(parsed), GOLD_TASK)
    assert result["grounding_recall"] == 1.0
    assert result["grounding_precision"] == pytest.approx(100 / 150)


def test_csag_style_exact_span_earns_full_credit() -> None:
    parsed = {
        "answer": "deep-branching algal lineage",
        "returned_spans": [{"document_id": GOLD_DOC, "start": 100, "end": 200}],
    }
    result = scorer.score_row(_row(parsed, condition="csag_rag"), GOLD_TASK)
    assert result["grounding_f1"] == 1.0
    assert result["grounding_precision"] == 1.0
    assert result["grounding_recall"] == 1.0


def test_legacy_id_echo_without_spans_earns_zero() -> None:
    # The old exploit: echo the gold ID, return no structured spans.
    parsed = {
        "answer": "deep-branching algal lineage",
        "evidence_ids": ["csag:evidence/doi:10.1038/s41467-025-67401-4/E0001"],
        "source_spans": ["P:100:200"],  # legacy string ref, must NOT be credited
        "returned_spans": [],
    }
    result = scorer.score_row(_row(parsed, condition="prose_rag"), GOLD_TASK)
    assert result["grounding_f1"] == 0.0
    assert result["grounding_recall"] == 0.0
    assert result["n_returned_spans"] == 0


def test_legacy_string_span_in_returned_spans_is_dropped() -> None:
    # Even placed under returned_spans, a bare-string ID is not a structured span.
    parsed = {
        "answer": "deep-branching algal lineage",
        "returned_spans": ["P:100:200", "csag:evidence/.../E0001"],
    }
    result = scorer.score_row(_row(parsed), GOLD_TASK)
    assert result["n_returned_spans"] == 0
    assert result["grounding_f1"] == 0.0


def test_symmetry_prose_and_csag_same_span_score_identically() -> None:
    # Condition-agnostic: identical spans -> identical grounding, regardless of
    # the 'condition' label. This is the core anti-circularity guarantee.
    span = [{"document_id": GOLD_DOC, "start": 130, "end": 205}]
    prose = scorer.score_row(
        _row({"answer": "x", "returned_spans": span}, condition="prose_rag"), GOLD_TASK
    )
    csag = scorer.score_row(
        _row({"answer": "x", "returned_spans": span}, condition="csag_rag"), GOLD_TASK
    )
    assert prose["grounding_f1"] == csag["grounding_f1"]
    assert prose["grounding_precision"] == csag["grounding_precision"]
    assert prose["grounding_recall"] == csag["grounding_recall"]


def test_non_overlapping_span_earns_zero() -> None:
    parsed = {"answer": "x", "returned_spans": [{"document_id": GOLD_DOC, "start": 300, "end": 400}]}
    result = scorer.score_row(_row(parsed), GOLD_TASK)
    assert result["grounding_f1"] == 0.0


def test_wrong_document_id_earns_zero() -> None:
    parsed = {"answer": "x", "returned_spans": [{"document_id": "OTHER", "start": 100, "end": 200}]}
    result = scorer.score_row(_row(parsed), GOLD_TASK)
    assert result["grounding_f1"] == 0.0


def test_oversized_covering_span_full_recall_low_precision() -> None:
    # Gold [100, 200) len=100. Returned [100, 600) len=500. overlap=100 chars.
    # The gold span IS fully covered -> recall 1.0 (coverage is representation-
    # fair), but the span is mostly off-target -> precision 100/500 = 0.2.
    parsed = {"answer": "x", "returned_spans": [{"document_id": GOLD_DOC, "start": 100, "end": 600}]}
    result = scorer.score_row(_row(parsed), GOLD_TASK)
    assert result["grounding_recall"] == 1.0
    assert result["grounding_precision"] == pytest.approx(0.2)
    assert result["grounding_f1"] == pytest.approx(2 * 1.0 * 0.2 / 1.2)


def test_precision_penalizes_extra_unmatched_span() -> None:
    # One on-target span [100,200) (100 chars) + one off-target span [900,950)
    # (50 chars). returned chars=150, on-target=100 -> precision 100/150, recall
    # 1.0. Extra off-target content lowers precision (character-level).
    parsed = {
        "answer": "x",
        "returned_spans": [
            {"document_id": GOLD_DOC, "start": 100, "end": 200},  # hit
            {"document_id": GOLD_DOC, "start": 900, "end": 950},  # miss
        ],
    }
    result = scorer.score_row(_row(parsed), GOLD_TASK)
    assert result["grounding_recall"] == 1.0
    assert result["grounding_precision"] == pytest.approx(100 / 150)
    assert result["grounding_f1"] == pytest.approx(2 * 1.0 * (100 / 150) / (1.0 + 100 / 150))


def test_dangerous_false_positive_unchanged() -> None:
    gold = {
        "id": "FP001",
        "task_type": "false_positive_filtering",
        "expected_decision": "reject",
        "gold_spans": [{"document_id": GOLD_DOC, "start": 10, "end": 20}],
    }
    promote = scorer.score_row(_row({"decision": "promote"}), gold)
    reject = scorer.score_row(_row({"decision": "reject"}), gold)
    assert promote["dangerous_false_positive"] == 1
    assert reject["dangerous_false_positive"] == 0


def test_scorer_source_never_reads_forbidden_id_fields() -> None:
    # Static guarantee: no forbidden gold/response ID field name appears as a
    # read in the scorer source. The only allowed mention is the explicit
    # FORBIDDEN_*_FIELDS guard tuples (and the module docstring), so we strip the
    # source of those before scanning.
    source = inspect.getsource(scorer)
    # Remove the docstring and the guard-tuple definitions from consideration.
    for marker in ("FORBIDDEN_GOLD_FIELDS", "FORBIDDEN_RESPONSE_FIELDS"):
        assert marker in source  # the guard tuples exist
    # Build the set of forbidden names and confirm none is ever indexed/.get().
    forbidden = set(scorer.FORBIDDEN_GOLD_FIELDS) | set(scorer.FORBIDDEN_RESPONSE_FIELDS)
    for field in forbidden:
        assert f'.get("{field}"' not in source, f"scorer must not .get({field!r})"
        assert f'["{field}"]' not in source, f"scorer must not index [{field!r}]"
        assert f"'{field}'" not in _read_calls(source), f"scorer must not read {field!r}"


def test_scorer_ignores_forbidden_fields_present_in_gold_and_response() -> None:
    # Behavioral guarantee: a task polluted with legacy circular fields, paired
    # with a response that ONLY supplies legacy IDs, scores grounding_f1 == 0.
    polluted_gold = {
        **GOLD_TASK,
        "required_evidence_ids": ["csag:evidence/doi:10.1038/.../E0001"],
        "required_span_ids": ["P:100:200"],
        "required_assertion_ids": ["csag:assertion/doi:10.1038/.../A0002"],
    }
    legacy_response = {
        "answer": "deep-branching algal lineage",
        "evidence_ids": ["csag:evidence/doi:10.1038/.../E0001"],
        "source_spans": ["P:100:200"],
    }
    result = scorer.score_row(_row(legacy_response), polluted_gold)
    assert result["grounding_f1"] == 0.0
    # Sanity: the gold's REAL span set is still what the scorer used.
    assert result["n_gold_spans"] == 1


def _read_calls(source: str) -> str:
    """Return source lines that look like dict reads, for the forbidden scan."""
    return "\n".join(
        line for line in source.splitlines() if ".get(" in line or "[" in line
    )


# --------------------------------------------------------------------------- #
# Generic five-task-type primary scorer (label normalization + free-text).
# Grounding (character coverage) is unchanged; these tests target the PRIMARY
# correctness routing only. Each case carries a 1-char gold span so grounding
# stays well-defined and does not interfere with the primary assertions.
# --------------------------------------------------------------------------- #
TINY_SPAN = [{"document_id": GOLD_DOC, "start": 10, "end": 11}]


def _label_gold(task_type: str, expected_label: str, **extra) -> dict:
    return {
        "id": f"L_{task_type}",
        "task_type": task_type,
        "expected_label": expected_label,
        "gold_spans": TINY_SPAN,
        **extra,
    }


# Each label task type: a correct label (incl. a synonym form) scores 1.0 and a
# wrong label scores 0.0. The model emits parsed_json['label'].
@pytest.mark.parametrize(
    "task_type, expected_label, correct_label, wrong_label",
    [
        # cross_paper_relation: agree/contradict/qualify/unrelated.
        ("cross_paper_relation", "contradict", "Contradicts", "agree"),
        ("cross_paper_relation", "unrelated", "independent", "agree"),
        # context_conditional: holds / does_not_hold.
        ("context_conditional", "holds", "True", "does_not_hold"),
        ("context_conditional", "does_not_hold", "violated", "holds"),
        # evidence_polarity: supports / refutes / inconclusive.
        ("evidence_polarity", "supports", "support", "refutes"),
        ("evidence_polarity", "refutes", "refute", "supports"),
        ("evidence_polarity", "inconclusive", "unclear", "supports"),
    ],
)
def test_label_task_correct_and_wrong(
    task_type: str, expected_label: str, correct_label: str, wrong_label: str
) -> None:
    gold = _label_gold(task_type, expected_label)
    correct = scorer.score_row(_row({"label": correct_label, "returned_spans": TINY_SPAN}), gold)
    wrong = scorer.score_row(_row({"label": wrong_label, "returned_spans": TINY_SPAN}), gold)
    assert correct["primary_correct"] == 1.0
    assert correct["label_correct"] == 1.0
    assert wrong["primary_correct"] == 0.0
    assert wrong["label_correct"] == 0.0


@pytest.mark.parametrize(
    "raw, canonical",
    [
        ("Contradicts", "contradict"),
        ("CONTRADICT", "contradict"),
        ("refute", "refutes"),
        ("refutes", "refutes"),
        ("support", "supports"),
        ("  Supports ", "supports"),
        ("true", "holds"),
        ("holds", "holds"),
        ("false", "does_not_hold"),
        ("violated", "does_not_hold"),
        ("does not hold", "does_not_hold"),
        ("qualifies", "qualify"),
        ("none", "unrelated"),
        ("independent", "unrelated"),
        ("unclear", "inconclusive"),
        ("agree", "agree"),  # unknown -> passthrough (lower/strip only)
    ],
)
def test_normalize_label_synonyms(raw: str, canonical: str) -> None:
    assert scorer.normalize_label(raw) == canonical


def test_normalize_label_synonyms_make_model_and_gold_match() -> None:
    # Behavioral proof that synonym folding drives the match: gold canonical
    # "contradict", model paraphrase "Contradicts" -> 1.0; the same model label
    # against gold "agree" -> 0.0.
    match = scorer.score_row(
        _row({"label": "Contradicts"}),
        _label_gold("cross_paper_relation", "contradict"),
    )
    mismatch = scorer.score_row(
        _row({"label": "Contradicts"}),
        _label_gold("cross_paper_relation", "agree"),
    )
    assert match["primary_correct"] == 1.0
    assert mismatch["primary_correct"] == 0.0


def test_relation_pair_routes_through_normalized_label_match() -> None:
    # The legacy relation_pair path must now succeed on a synonym via the same
    # normalized matcher (fixes the prior too-strict exact match ~0.12). Both the
    # canonical expected_label and the legacy expected_relation_label alias work.
    gold_new = {
        "id": "R1",
        "task_type": "relation_pair",
        "expected_label": "contradict",
        "gold_spans": TINY_SPAN,
    }
    gold_legacy = {
        "id": "R2",
        "task_type": "relation_pair",
        "expected_relation_label": "contradict",
        "gold_spans": TINY_SPAN,
    }
    syn = scorer.score_row(_row({"label": "Contradicts"}), gold_new)
    legacy = scorer.score_row(_row({"label": "contradict"}), gold_legacy)
    wrong = scorer.score_row(_row({"label": "agree"}), gold_new)
    assert syn["primary_correct"] == 1.0
    assert legacy["primary_correct"] == 1.0
    assert wrong["primary_correct"] == 0.0


def test_empty_model_label_scores_zero() -> None:
    gold = _label_gold("evidence_polarity", "supports")
    result = scorer.score_row(_row({"returned_spans": TINY_SPAN}), gold)  # no 'label'
    assert result["primary_correct"] == 0.0
    assert result["label_correct"] == 0.0


@pytest.mark.parametrize("task_type", ["multi_hop", "cross_paper_synthesis", "context_qa"])
def test_free_text_tasks_use_answer_overlap(task_type: str) -> None:
    # Free-text tasks keep paraphrase-tolerant token-overlap on 'answer' and do
    # NOT consult 'label'. A label-only response scores 0; a high-overlap answer
    # scores 1.0.
    gold = {
        "id": f"F_{task_type}",
        "task_type": task_type,
        "answer": "deep-branching algal lineage early diverging",
        "gold_spans": TINY_SPAN,
    }
    # Label present but no answer overlap -> free-text scorer ignores label -> 0.
    label_only = scorer.score_row(
        _row({"label": "supports", "returned_spans": TINY_SPAN}), gold
    )
    assert label_only["primary_correct"] == 0.0
    assert label_only["label_correct"] is None  # free-text path never sets label_correct

    # Paraphrased answer with sufficient token recall -> 1.0.
    good = scorer.score_row(
        _row(
            {
                "answer": "an early diverging deep-branching algal lineage was recovered",
                "returned_spans": TINY_SPAN,
            }
        ),
        gold,
    )
    assert good["answer_correct"] == 1.0
    assert good["primary_correct"] == 1.0


def test_label_task_grounding_is_unchanged_character_coverage() -> None:
    # Sanity: switching to label scoring does not perturb grounding. An exact
    # gold-span return still yields f1 == 1.0 on a label task, and a whole-doc
    # span still collapses precision -> the anti-gaming guarantee is intact.
    gold = _label_gold("cross_paper_relation", "agree")
    exact = scorer.score_row(
        _row({"label": "agree", "returned_spans": [{"document_id": GOLD_DOC, "start": 10, "end": 11}]}),
        gold,
    )
    assert exact["grounding_f1"] == 1.0
    huge = scorer.score_row(
        _row({"label": "agree", "returned_spans": [{"document_id": GOLD_DOC, "start": 0, "end": 5000}]}),
        gold,
    )
    assert huge["grounding_recall"] == 1.0
    assert huge["grounding_precision"] < 0.01
