"""Exercise request-only access through the public paper-local validator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from csag import validate_extraction
from csag.paths import ROOT

TOY = ROOT / "examples/toy"
FIXTURE = ROOT / "tests/fixtures/request_only_dataset/availability.json"
REAL_STATEMENT = json.loads(FIXTURE.read_text(encoding="utf-8"))["source_statement"]


def _write_case(
    folder: Path,
    statement: str,
    *,
    quote: str | None = None,
    heading: str = "Data availability",
    span_changes: dict[str, object] | None = None,
    dataset_changes: dict[str, object] | None = None,
) -> tuple[Path, Path]:
    extraction = json.loads((TOY / "paper_extraction.json").read_text(encoding="utf-8"))
    source = (TOY / "toy.md").read_text(encoding="utf-8")
    source += f"\n\n## {heading}\n\n{statement}\n"
    quote = statement if quote is None else quote
    start = source.index(quote)
    dataset = {
        "id": f"csag:dataset/{extraction['id']}/REQUEST1",
        "label": "Study datasets available on request",
        "text_spans": [
            {
                "id": f"csag:span/{extraction['id']}/REQUEST1",
                "document_id": extraction["id"],
                "section_type": "other",
                "start_char": start,
                "end_char": start + len(quote),
                "exact_text": quote,
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
        "The data are available on request.",
        "All datasets are obtainable upon reasonable request from the authors.",
        "Sequence data are available on request.",
        "Data availability: The datasets are available on request.",
        "The data can be obtained from the authors upon reasonable request.",
        "The data are available on request from Dr. Smith.",
        "The data are available on request at no cost.",
        "The data collected after treatment are available on request.",
        "The data collected with informed consent are available on request.",
        "The data collected after ethics approval are available on request.",
        "The data are available on request from Smith et al.",
        "Data available on request from the authors.",
        (
            "Data are not publicly available due to privacy requirements but are "
            "available upon reasonable request from the corresponding author."
        ),
    ],
)
def test_grounded_request_only_dataset_passes(tmp_path: Path, statement: str) -> None:
    graph, source = _write_case(tmp_path, statement)

    result = validate_extraction(graph, source_markdown=source, profile="paper_local")

    assert result.ok, result.stdout + result.stderr


@pytest.mark.parametrize(
    "statement",
    [
        "The data are not available on request.",
        "No data are available on request.",
        "The data will be available on request.",
        "The data should be available on request.",
        "We recommend that the data are available on request.",
        "If approval is obtained,\nthe data are available on request.",
        "If approval is obtained, the data are available on request.",
        "The data are available on request if approval is obtained.",
        "The data are available on request unless the authors refuse.",
        "The data are available on request?",
        "Neither data nor code are available on request.",
        "The data are available on request after publication.",
        "The data are available on request once the embargo ends.",
        "None of the data are available on request.",
        "The data are available on request only with ethics approval.",
        "The data are available on request starting next year.",
        "No study data are available on request.",
        "The data are available on request after ethics approval.",
        "The data are available on request after January 2027.",
        "The data are available on request with permission of the ministry.",
        (
            "De-identified aggregate data are available upon reasonable request "
            "and approval."
        ),
        "The data are available on request from January 2027.",
        "The data are available on request but not to commercial users.",
    ],
)
def test_negative_or_conditional_request_statement_fails(
    tmp_path: Path, statement: str
) -> None:
    graph, source = _write_case(tmp_path, statement)

    result = validate_extraction(graph, source_markdown=source, profile="paper_local")

    assert not result.ok
    assert "missing accession, repository, or dataset URL" in result.stdout


@pytest.mark.parametrize(
    "statement",
    [
        "It is not true that the data are available on request.",
        "If approval is obtained, the data are available on request.",
        "If approval is obtained,\nthe data are available on request.",
        "We recommend that the data are available on request.",
    ],
)
def test_cropped_positive_clause_cannot_hide_qualifier(
    tmp_path: Path, statement: str
) -> None:
    graph, source = _write_case(
        tmp_path, statement, quote="the data are available on request."
    )

    result = validate_extraction(graph, source_markdown=source, profile="paper_local")

    assert not result.ok


@pytest.mark.parametrize(
    "statement",
    [
        "Data availability: The data are available on request.",
        "**Data availability:** The data are available on request.",
        "**Data availability.** The data are available on request.",
    ],
)
def test_label_before_positive_clause_passes(tmp_path: Path, statement: str) -> None:
    graph, source = _write_case(
        tmp_path, statement, quote="The data are available on request."
    )

    result = validate_extraction(graph, source_markdown=source, profile="paper_local")

    assert result.ok, result.stdout + result.stderr


def test_span_cannot_end_at_an_abbreviation(tmp_path: Path) -> None:
    graph, source = _write_case(
        tmp_path,
        "The data are available on request from Dr. Smith only after ethics approval.",
        quote="The data are available on request from Dr.",
    )

    result = validate_extraction(graph, source_markdown=source, profile="paper_local")

    assert not result.ok


def test_span_cannot_stop_inside_a_sentence(tmp_path: Path) -> None:
    graph, source = _write_case(
        tmp_path,
        "The data are available on request from Smith et al. after approval.",
        quote="The data are available on request from Smith et al.",
    )

    result = validate_extraction(graph, source_markdown=source, profile="paper_local")

    assert not result.ok


def test_availability_of_data_heading_triggers_the_dataset_check(
    tmp_path: Path,
) -> None:
    graph, source = _write_case(
        tmp_path,
        "The data are not available on request.",
        heading="Availability of data and materials",
    )

    result = validate_extraction(graph, source_markdown=source, profile="paper_local")

    assert not result.ok
    assert "missing accession, repository, or dataset URL" in result.stdout


def test_label_with_condition_cannot_hide_qualifier(tmp_path: Path) -> None:
    graph, source = _write_case(
        tmp_path,
        "If approved: the data are available on request.",
        quote="the data are available on request.",
    )

    result = validate_extraction(graph, source_markdown=source, profile="paper_local")

    assert not result.ok


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
def test_request_availability_requires_exact_current_grounding(
    tmp_path: Path, changes: dict[str, object]
) -> None:
    graph, source = _write_case(tmp_path, REAL_STATEMENT, span_changes=changes)

    result = validate_extraction(graph, source_markdown=source, profile="paper_local")

    assert not result.ok


def test_request_availability_requires_dataset_owned_span(tmp_path: Path) -> None:
    graph, source = _write_case(
        tmp_path, REAL_STATEMENT, dataset_changes={"text_spans": []}
    )

    result = validate_extraction(graph, source_markdown=source, profile="paper_local")

    assert not result.ok


def test_request_availability_still_requires_dataset_object(tmp_path: Path) -> None:
    graph, source = _write_case(tmp_path, REAL_STATEMENT)
    extraction = json.loads(graph.read_text(encoding="utf-8"))
    extraction["datasets"] = []
    graph.write_text(json.dumps(extraction), encoding="utf-8")

    result = validate_extraction(graph, source_markdown=source, profile="paper_local")

    assert not result.ok
    assert "extraction.datasets is empty" in result.stdout
