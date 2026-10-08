"""Check source grounding for Dataset objects with optional identifiers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from csag import validate_extraction
from csag.paths import ROOT

TOY = ROOT / "examples/toy"
FIXTURE = ROOT / "tests/fixtures/request_only_dataset/availability.json"
REAL_STATEMENT = json.loads(FIXTURE.read_text(encoding="utf-8"))["source_statement"]
PRIMER_STATEMENT = "Primer sequences are available upon request."


def _write_case(
    folder: Path,
    statement: str,
    *,
    span_changes: dict[str, object] | None = None,
    dataset_changes: dict[str, object] | None = None,
) -> tuple[Path, Path]:
    extraction = json.loads((TOY / "paper_extraction.json").read_text(encoding="utf-8"))
    source = (TOY / "toy.md").read_text(encoding="utf-8")
    source += f"\n\n## Data availability\n\n{statement}\n"
    start = source.index(statement)
    dataset = {
        "id": f"csag:dataset/{extraction['id']}/REQUEST1",
        "label": "Study datasets available on request",
        "text_spans": [
            {
                "id": f"csag:span/{extraction['id']}/REQUEST1",
                "document_id": extraction["id"],
                "section_type": "other",
                "start_char": start,
                "end_char": start + len(statement),
                "exact_text": statement,
                **(span_changes or {}),
            }
        ],
        **(dataset_changes or {}),
    }
    extraction["datasets"] = [dataset]
    graph_path, source_path = folder / "graph.json", folder / "source.md"
    graph_path.write_text(json.dumps(extraction), encoding="utf-8")
    source_path.write_text(source, encoding="utf-8")
    return graph_path, source_path


@pytest.mark.parametrize(
    "statement",
    [
        REAL_STATEMENT,
        PRIMER_STATEMENT,
    ],
)
def test_grounded_request_only_dataset_passes(tmp_path: Path, statement: str) -> None:
    graph, source = _write_case(tmp_path, statement)

    result = validate_extraction(graph, source_markdown=source, profile="paper_local")

    assert result.ok, result.stdout + result.stderr


@pytest.mark.parametrize(
    "changes",
    [
        {"start_char": 0},
        {"end_char": 999999},
        {"start_char": True},
        {"document_id": "pmid:99999999"},
        {"exact_text": "The data are available on request."},
    ],
)
@pytest.mark.parametrize("statement", [REAL_STATEMENT, PRIMER_STATEMENT])
@pytest.mark.parametrize("identifiers", [{}, {"repository": "Source archive"}])
def test_dataset_span_requires_exact_current_grounding(
    tmp_path: Path,
    changes: dict[str, object],
    statement: str,
    identifiers: dict[str, object],
) -> None:
    graph, source = _write_case(
        tmp_path, statement, span_changes=changes, dataset_changes=identifiers
    )

    result = validate_extraction(graph, source_markdown=source, profile="paper_local")

    assert not result.ok


@pytest.mark.parametrize("statement", [REAL_STATEMENT, PRIMER_STATEMENT])
def test_dataset_spans_are_optional(tmp_path: Path, statement: str) -> None:
    graph, source = _write_case(tmp_path, statement, dataset_changes={"text_spans": []})

    result = validate_extraction(graph, source_markdown=source, profile="paper_local")

    assert result.ok, result.stdout + result.stderr
