#!/usr/bin/env python3
"""Span-anchored, non-circular scorer for the CSAG retrieval benchmark (v2).

This scorer fixes the identifier-namespace confound in ``scripts/score_eval.py``.
The legacy scorer compared model-returned IDs against CSAG-native gold IDs
(e.g. ``csag:evidence/...//E0001`` and ``doi:...:10722:11035``). The ``csag_rag``
packet literally contains those IDs, so the model echoes them; the ``prose_rag``
packet only carries markdown-chunk IDs in a DISJOINT namespace, so prose can
NEVER match a gold ID. The resulting prose-vs-CSAG "grounding gains" were an
artifact of the ID scheme, not retrieval quality.

CORRECTED DESIGN (this file):

1. Grounding gold is expressed ONLY as paper-anchored CHARACTER intervals
   ``{document_id, start, end}`` into the canonical paper Markdown that BOTH
   conditions retrieve from. There are NO ``csag:`` IDs anywhere in gold.
2. The model response contract is IDENTICAL for both conditions:
   ``{answer, returned_spans: [{document_id, start, end}], decision/label}``.
3. Scoring is condition-agnostic (same code path for ``prose_rag`` and
   ``csag_rag``):
     - primary (task-type dependent, same code path for both conditions):
       * FREE-TEXT tasks (multi_hop, cross_paper_synthesis, context_qa):
         paraphrase-tolerant token-overlap answer match.
       * LABEL tasks (cross_paper_relation, context_conditional,
         evidence_polarity, relation_pair): 1.0 iff the normalized model label
         equals the normalized gold expected_label, where normalization
         lowercases, strips, and folds common synonyms (contradicts->contradict,
         refute(s)->refutes, support(s)->supports, holds/true->holds,
         does_not_hold/false/violated->does_not_hold, qualifies->qualify,
         none/unrelated/independent->unrelated, inconclusive/unclear->
         inconclusive). This replaces the prior too-strict exact label match.
       * otherwise: decision/claim-class correctness;
     - grounding precision/recall/F1 via CHARACTER coverage: with merged gold
       character set G, merged returned character set R, and overlap O = |R n G|,
       recall = O/|G| and precision = O/|R|. Recall (gold coverage) is
       representation-fair -- a coarse prose chunk and a tight CSAG object span
       that both cover the same gold sentence score recall 1.0 identically. It is
       NOT gameable by a single whole-document span: that span gets recall 1.0 but
       precision |G|/|R| -> ~0, collapsing F1.
     - ``dangerous_false_positive``: gold says reject but model promotes.
4. IDs are never read or credited. Only structured character spans count toward
   grounding, which kills the echo-the-ID exploit.

This module is self-contained and does NOT import or modify ``score_eval.py``.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSONL row: {exc}") from exc
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def relpath(path: Path, root: Path = ROOT) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def word_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_.:/-]*", normalize_text(value))
        if len(token) > 2
    }


def flatten_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        values: list[str] = []
        for nested in value.values():
            values.extend(flatten_strings(nested))
        return values
    if isinstance(value, list):
        values = []
        for nested in value:
            values.extend(flatten_strings(nested))
        return values
    return [str(value)]

# Paraphrase tolerance for token-overlap answer matching (mirrors the accepted
# answer_accuracy behavior: a gold answer is satisfied at >= 0.55 token recall).
ANSWER_TOKEN_RECALL_THRESHOLD = 0.55

# Field names the v2 scorer is FORBIDDEN from reading. They belong to the
# circular legacy gold/response contract. Presence here is asserted-against in
# tests/test_score_eval_v2.py to keep the exploit dead.
FORBIDDEN_GOLD_FIELDS = (
    "required_evidence_ids",
    "required_assertion_ids",
    "required_context_ids",
    "required_span_ids",
    "required_relation_ids",
    "required_cross_relation_ids",
    "required_caveat_or_gap_ids",
)
FORBIDDEN_RESPONSE_FIELDS = (
    "evidence_ids",
    "assertion_ids",
    "source_ids",
    "relation_ids",
    "context_ids",
    "source_spans",
)


# --------------------------------------------------------------------------- #
# Span normalization and interval-overlap matching
# --------------------------------------------------------------------------- #
def normalize_span(span: Any) -> dict[str, Any] | None:
    """Coerce a span into ``{document_id, start, end}`` or return ``None``.

    Only structured character spans are accepted. Bare string IDs (legacy
    ``"doi:...:10722:11035"`` refs or ``csag:evidence/...`` echoes) are rejected
    on purpose: the v2 scorer credits spans, never identifiers.
    """
    if not isinstance(span, dict):
        return None
    document_id = span.get("document_id")
    start = span.get("start")
    end = span.get("end")
    if not isinstance(document_id, str) or not document_id:
        return None
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
        return None
    start_int = int(start)
    end_int = int(end)
    if end_int < start_int:
        start_int, end_int = end_int, start_int
    return {"document_id": document_id, "start": start_int, "end": end_int}


def normalize_spans(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    out: list[dict[str, Any]] = []
    for value in values:
        normalized = normalize_span(value)
        if normalized is not None:
            out.append(normalized)
    return out


def _merge_intervals_by_doc(spans: list[dict[str, Any]]) -> dict[str, list[tuple[int, int]]]:
    """Group spans by ``document_id`` and merge overlapping/adjacent intervals.

    Returns disjoint, sorted intervals per document so each character is counted
    once even when input spans overlap each other.
    """
    by_doc: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for span in spans:
        by_doc[span["document_id"]].append((span["start"], span["end"]))
    merged: dict[str, list[tuple[int, int]]] = {}
    for document_id, intervals in by_doc.items():
        intervals.sort()
        out: list[tuple[int, int]] = []
        for start, end in intervals:
            if out and start <= out[-1][1]:
                out[-1] = (out[-1][0], max(out[-1][1], end))
            else:
                out.append((start, end))
        merged[document_id] = out
    return merged


def _total_length(merged: dict[str, list[tuple[int, int]]]) -> int:
    return sum(end - start for intervals in merged.values() for start, end in intervals)


def _intersection_length(
    a: dict[str, list[tuple[int, int]]],
    b: dict[str, list[tuple[int, int]]],
) -> int:
    """Total characters covered by BOTH a and b, summed per document."""
    total = 0
    for document_id, a_intervals in a.items():
        b_intervals = b.get(document_id)
        if not b_intervals:
            continue
        for a_start, a_end in a_intervals:
            for b_start, b_end in b_intervals:
                total += max(0, min(a_end, b_end) - max(a_start, b_start))
    return total


def grounding_scores(
    gold_spans: list[dict[str, Any]],
    returned_spans: list[dict[str, Any]],
) -> dict[str, float]:
    """Character-coverage precision/recall/F1 (condition-agnostic, non-gameable).

    Let G be the merged gold character set, R the merged returned character set,
    and O = |R n G| the characters they share:

      * recall    = O / |G|   (fraction of gold characters the model covered)
      * precision = O / |R|   (fraction of returned characters that are on-target)
      * f1        = harmonic mean of the two

    Symmetric by construction: the same character overlap O drives both sides, so
    a coarse prose chunk and a tight CSAG object span that cover the same gold
    score recall identically -- recall is the representation-fair grounding
    signal. Precision additionally rewards tight grounding and, crucially, makes
    the metric non-gameable: a single whole-document span gets recall 1.0 but
    precision |G|/|R| -> ~0, so F1 collapses. IDs are never consulted.
    """
    gold = _merge_intervals_by_doc(gold_spans)
    returned = _merge_intervals_by_doc(returned_spans)
    gold_len = _total_length(gold)
    returned_len = _total_length(returned)

    if gold_len == 0 and returned_len == 0:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if gold_len == 0:
        # No grounding gold to cover; any returned characters are false positives.
        return {"precision": 0.0, "recall": 1.0, "f1": 0.0}
    if returned_len == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    overlap = _intersection_length(returned, gold)
    precision = overlap / returned_len
    recall = overlap / gold_len
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


# --------------------------------------------------------------------------- #
# Primary correctness (condition-neutral)
# --------------------------------------------------------------------------- #
def answer_accuracy(gold: dict[str, Any], parsed: dict[str, Any]) -> float:
    """Paraphrase-tolerant token-overlap answer match (accepted v1 logic)."""
    expected_strings = flatten_strings(gold.get("answer"))
    observed_strings = flatten_strings(parsed.get("answer"))
    if not expected_strings:
        return 0.0
    observed_tokens = word_tokens(" ".join(observed_strings))
    if not observed_tokens:
        return 0.0
    recalls: list[float] = []
    for expected in expected_strings:
        expected_tokens = word_tokens(expected)
        if not expected_tokens:
            continue
        recalls.append(len(expected_tokens & observed_tokens) / len(expected_tokens))
    if not recalls:
        return 0.0
    return 1.0 if statistics.mean(recalls) >= ANSWER_TOKEN_RECALL_THRESHOLD else 0.0


def normalized_decision(value: Any) -> str:
    text = str(value or "").lower().strip()
    if text in {"accept", "accepted", "support", "supported", "promote", "promoted"}:
        return "promote"
    if text in {"reject", "rejected", "unsupported", "deny", "decline"}:
        return "reject"
    return text


# Label task types whose correctness is a normalized exact-label match. Both the
# model label and the gold expected_label pass through ``normalize_label`` so
# common synonyms collapse to a single canonical token before comparison.
LABEL_TASK_TYPES = frozenset(
    {
        "cross_paper_relation",
        "context_conditional",
        "evidence_polarity",
        "relation_pair",
        "relation_pairs",
    }
)

# Free-text task types scored by paraphrase-tolerant token-overlap on ``answer``.
FREE_TEXT_TASK_TYPES = frozenset(
    {
        "multi_hop",
        "cross_paper_synthesis",
        "context_qa",
        "context_sensitive_qa",
    }
)

# Synonym map applied AFTER lowercasing/stripping. Every label produced by a
# model or stored in gold is folded through this table so that, e.g.,
# "Contradicts." and "contradict" compare equal. Keys are already
# lowercased+stripped; the canonical value on the right is what the comparison
# uses. Labels not present here pass through unchanged (after lower/strip).
_LABEL_SYNONYMS = {
    "contradicts": "contradict",
    "contradicted": "contradict",
    "refute": "refutes",
    "refuted": "refutes",
    "support": "supports",
    "supported": "supports",
    "holds": "holds",
    "true": "holds",
    "does_not_hold": "does_not_hold",
    "does not hold": "does_not_hold",
    "false": "does_not_hold",
    "violated": "does_not_hold",
    "qualifies": "qualify",
    "qualified": "qualify",
    "none": "unrelated",
    "unrelated": "unrelated",
    "independent": "unrelated",
    "inconclusive": "inconclusive",
    "unclear": "inconclusive",
}


def normalize_label(value: Any) -> str:
    """Lowercase, strip, and map common synonyms to a canonical label token.

    Applied identically to the model label and the gold ``expected_label`` so a
    correct-but-paraphrased label (e.g. "Contradicts" vs "contradict",
    "refute" vs "refutes", "true" vs "holds") scores as a match. This replaces
    the prior too-strict exact-string comparison on relation labels that scored
    ~0.12. Unknown labels fall through unchanged after lowercasing/stripping.
    """
    text = str(value or "").lower().strip()
    return _LABEL_SYNONYMS.get(text, text)


def score_primary(
    gold: dict[str, Any], parsed: dict[str, Any]
) -> dict[str, Any]:
    """Compute the condition-neutral primary metric for a task.

    Returns the per-task-type breakdown plus ``primary_correct`` and
    ``dangerous_false_positive``. ``task_type`` drives which sub-metric is the
    primary; identical code path for every condition.
    """
    task_type = gold.get("task_type", "")
    result: dict[str, Any] = {
        "answer_correct": None,
        "label_correct": None,
        "decision_correct": None,
        "claim_class_correct": None,
        "dangerous_false_positive": False,
    }

    if task_type in FREE_TEXT_TASK_TYPES:
        answer_correct = answer_accuracy(gold, parsed)
        result["answer_correct"] = answer_correct
        result["primary_correct"] = answer_correct
        return result

    if task_type in LABEL_TASK_TYPES:
        observed = normalize_label(parsed.get("label"))
        # Canonical gold field is ``expected_label``; ``expected_relation_label``
        # is kept as a legacy alias so existing relation_pair gold still scores.
        expected_raw = gold.get("expected_label")
        if expected_raw is None:
            expected_raw = gold.get("expected_relation_label")
        expected = normalize_label(expected_raw)
        label_correct = 1.0 if expected and observed == expected else 0.0
        result["label_correct"] = label_correct
        result["primary_correct"] = label_correct
        return result

    # Default: claim-filtering / false-positive style decision task.
    observed_decision = normalized_decision(parsed.get("decision"))
    expected_decision = normalized_decision(gold.get("expected_decision"))
    decision_correct = 1.0 if observed_decision == expected_decision else 0.0
    observed_class = str(parsed.get("claim_class", "")).lower().strip()
    expected_class = str(gold.get("claim_class", "")).lower().strip()
    # Claim class is only scored when the gold provides one.
    if expected_class:
        claim_class_correct = 1.0 if observed_class == expected_class else 0.0
    else:
        claim_class_correct = None
    result["decision_correct"] = decision_correct
    result["claim_class_correct"] = claim_class_correct
    if claim_class_correct is None:
        result["primary_correct"] = decision_correct
    else:
        result["primary_correct"] = 1.0 if decision_correct and claim_class_correct else 0.0
    result["dangerous_false_positive"] = (
        expected_decision == "reject" and observed_decision == "promote"
    )
    return result


# --------------------------------------------------------------------------- #
# Row scoring
# --------------------------------------------------------------------------- #
def gold_spans_of(gold: dict[str, Any]) -> list[dict[str, Any]]:
    """Read paper-anchored gold spans, never IDs.

    Accepts ``gold_spans`` (canonical) and ``grounding_gold`` as aliases. Each
    entry must be a ``{document_id, start, end}`` character interval.
    """
    raw = gold.get("gold_spans")
    if raw is None:
        raw = gold.get("grounding_gold")
    return normalize_spans(raw)


def returned_spans_of(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    """Read the model's structured spans, never IDs.

    The canonical response field is ``returned_spans``. Bare-string entries are
    dropped by ``normalize_spans`` so legacy ID echoes earn no credit.
    """
    return normalize_spans(parsed.get("returned_spans"))


def score_row(row: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    """Score one model run row against its span-anchored gold task.

    Condition-agnostic: ``prose_rag`` and ``csag_rag`` traverse identical logic.
    """
    parsed = row.get("parsed_json")
    invalid_json = not isinstance(parsed, dict)
    parsed = parsed if isinstance(parsed, dict) else {}

    primary = score_primary(gold, parsed)
    grounding = grounding_scores(gold_spans_of(gold), returned_spans_of(parsed))

    return {
        "task_id": row.get("task_id", gold.get("id", "")),
        "task_name": row.get("task_name") or gold.get("_task_name", ""),
        "task_type": gold.get("task_type", ""),
        "condition": row.get("condition", ""),
        "model": row.get("model", ""),
        "invalid_json": int(invalid_json),
        "primary_correct": float(primary.get("primary_correct") or 0.0),
        "answer_correct": primary["answer_correct"],
        "label_correct": primary["label_correct"],
        "decision_correct": primary["decision_correct"],
        "claim_class_correct": primary["claim_class_correct"],
        "grounding_precision": grounding["precision"],
        "grounding_recall": grounding["recall"],
        "grounding_f1": grounding["f1"],
        "n_gold_spans": len(gold_spans_of(gold)),
        "n_returned_spans": len(returned_spans_of(parsed)),
        "dangerous_false_positive": int(bool(primary["dangerous_false_positive"])),
    }


# --------------------------------------------------------------------------- #
# IO / aggregation / CLI
# --------------------------------------------------------------------------- #
def load_gold_tasks(tasks_path: Path) -> dict[str, dict[str, Any]]:
    tasks: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(tasks_path):
        task_id = row.get("id")
        if task_id is None:
            raise ValueError(f"{tasks_path}: gold task missing required 'id' field")
        tasks[task_id] = row
    return tasks


def mean(values: list[Any]) -> float:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    return statistics.mean(numeric) if numeric else 0.0


def summarize(scores: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in scores:
        grouped[tuple(row.get(key, "") for key in keys)].append(row)
    summaries: list[dict[str, Any]] = []
    for group_values, rows in sorted(grouped.items(), key=lambda item: [str(v) for v in item[0]]):
        summary = {key: value for key, value in zip(keys, group_values)}
        summary.update(
            {
                "n": len(rows),
                "primary_accuracy": mean([row["primary_correct"] for row in rows]),
                "invalid_json_rate": mean([row["invalid_json"] for row in rows]),
                "grounding_precision": mean([row["grounding_precision"] for row in rows]),
                "grounding_recall": mean([row["grounding_recall"] for row in rows]),
                "grounding_f1": mean([row["grounding_f1"] for row in rows]),
                "dangerous_false_positive_rate": mean(
                    [row["dangerous_false_positive"] for row in rows]
                ),
            }
        )
        summaries.append(summary)
    return summaries


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Span-anchored, non-circular CSAG retrieval benchmark scorer (v2)."
    )
    parser.add_argument("--tasks", type=Path, required=True, help="Gold tasks JSONL with span-anchored grounding gold.")
    parser.add_argument("--runs", type=Path, required=True, help="Model run rows JSONL (identical contract for both conditions).")
    parser.add_argument("--out-dir", type=Path, required=True, help="Directory for score outputs.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        gold = load_gold_tasks(args.tasks)
        run_rows = read_jsonl(args.runs)
    except Exception as exc:  # noqa: BLE001 - surface a clean CLI error
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if not run_rows:
        print(f"ERROR: no run rows found in {args.runs}", file=sys.stderr)
        return 1

    scores: list[dict[str, Any]] = []
    for row in run_rows:
        task_id = row.get("task_id")
        if task_id not in gold:
            print(f"ERROR: run row references unknown task_id {task_id}", file=sys.stderr)
            return 1
        scores.append(score_row(row, gold[task_id]))

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "per_item_scores.jsonl", scores)
    write_tsv(out_dir / "summary_by_model.tsv", summarize(scores, ["model", "condition"]))
    write_tsv(out_dir / "summary_by_task.tsv", summarize(scores, ["task_name", "condition"]))
    write_json(
        out_dir / "score_manifest.json",
        {
            "ok": True,
            "scorer": "score_eval_v2",
            "tasks": relpath(args.tasks),
            "runs": relpath(args.runs),
            "scored_rows": len(scores),
        },
    )
    print(json.dumps({"ok": True, "scored_rows": len(scores), "out_dir": str(out_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
