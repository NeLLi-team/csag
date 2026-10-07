"""Distinguish temporal prose from deposits through the public CSAG APIs."""

import json
from pathlib import Path
from typing import NamedTuple

import pytest

from csag import build_quality_report, validate_extraction

TEMPORAL = [
    "Resources are available at a given time in terms of measured capacity.",
    "Resources are AVAILABLE AT\t A GIVEN TIME IN TERMS OF measured capacity.",
]
DEPOSITS = [
    "Data are available at the European Genome-phenome Archive.",
    "Data are available at the Wellcome Sanger Institute.",
    "Data are available at the Time of Flight Data Centre.",
    "Data are available at present.org/data.",
    "Data are available at https://example.org/data.",
]
STRONG_SIGNALS = [
    "Resources are available at the time of publication.",
    "We describe data availability.",
    "We describe availability of data.",
    "The accession is SYN001.",
    "The project id is SYN001.",
    "We used a repository.",
    "We used Zenodo.",
    "We used IMG/M.",
    "We used a data portal.",
    "We used SRA.",
    "We used GEO.",
    "We used PRIDE.",
    "Records were downloaded at the institute.",
    "Resources are available at a given time in terms of capacity. We used SRA.",
]


class SourceCase(NamedTuple):
    """Paths to the generated graph and its two independent source forms."""

    graph: Path
    source_markdown: Path
    article_json: Path


@pytest.mark.parametrize("statement", TEMPORAL)
def test_temporal_prose_passes_paper_local(tmp_path: Path, statement: str) -> None:
    """A time qualifier alone does not require a Dataset."""
    case = _write_case(tmp_path, statement)

    validation = validate_extraction(
        case.graph, source_markdown=case.source_markdown, profile="paper_local"
    )

    assert validation.exit_code == 0, validation.stdout + validation.stderr
    assert validation.ok is True
    assert validation.data is not None
    assert validation.data["errors"] == []
    assert "extraction.datasets is empty" not in validation.stdout


@pytest.mark.parametrize("statement", TEMPORAL)
@pytest.mark.parametrize("source_kind", ["source_markdown", "article_json"])
def test_temporal_prose_passes_strict_quality(
    tmp_path: Path, statement: str, source_kind: str
) -> None:
    """Temporal prose passes full-article quality in either source format."""
    case = _write_case(tmp_path, statement)

    quality = build_quality_report(
        case.graph,
        strict=True,
        document_scope="full_article",
        **{source_kind: getattr(case, source_kind)},
    )

    assert quality.exit_code == 0, quality.stdout + quality.stderr
    assert quality.ok is True
    assert quality.data is not None
    assert quality.data["source_signals"]["dataset_signal_present"] is False
    assert quality.data["issues"] == []
    assert _dataset_status(quality.data, "completeness") == "pass"
    assert _dataset_status(quality.data, "density") == "pass"


@pytest.mark.parametrize("statement", DEPOSITS + STRONG_SIGNALS)
def test_deposit_signals_require_dataset(tmp_path: Path, statement: str) -> None:
    """Each isolated signal still requires a Dataset through both APIs."""
    case = _write_case(tmp_path, statement)

    validation = validate_extraction(
        case.graph, source_markdown=case.source_markdown, profile="paper_local"
    )
    quality = build_quality_report(
        case.graph,
        source_markdown=case.source_markdown,
        strict=True,
        document_scope="full_article",
    )

    assert validation.exit_code == 1
    assert validation.ok is False
    assert validation.data is not None
    assert len(validation.data["errors"]) == 1
    assert "extraction.datasets is empty" in validation.stdout
    assert quality.exit_code == 1
    assert quality.ok is False
    assert quality.data is not None
    assert quality.data["source_signals"]["dataset_signal_present"] is True
    assert _dataset_status(quality.data, "completeness") == "fail"
    assert _dataset_status(quality.data, "density") == "warn"


@pytest.mark.parametrize("statement", DEPOSITS)
def test_article_only_deposit_requires_dataset(tmp_path: Path, statement: str) -> None:
    """Sidecar-only deposits retain both quality requirements."""
    case = _write_case(tmp_path, statement)

    quality = build_quality_report(
        case.graph,
        article_json=case.article_json,
        strict=True,
        document_scope="full_article",
    )

    assert quality.exit_code == 1
    assert quality.ok is False
    assert quality.data is not None
    assert quality.data["source_signals"]["dataset_signal_present"] is True
    assert _dataset_status(quality.data, "completeness") == "fail"
    assert _dataset_status(quality.data, "density") == "warn"


def test_represented_deposit_passes(tmp_path: Path) -> None:
    """A repository Dataset satisfies validation and full-article quality."""
    case = _write_case(
        tmp_path,
        "Data are available at the European Genome-phenome Archive.",
        datasets=[
            {
                "id": "csag:dataset/synthetic/D1",
                "repository": "European Genome-phenome Archive",
            }
        ],
    )

    validation = validate_extraction(
        case.graph, source_markdown=case.source_markdown, profile="paper_local"
    )
    quality = build_quality_report(
        case.graph,
        source_markdown=case.source_markdown,
        strict=True,
        document_scope="full_article",
    )

    assert validation.exit_code == 0, validation.stdout + validation.stderr
    assert validation.ok is True
    assert quality.exit_code == 0, quality.stdout + quality.stderr
    assert quality.ok is True
    assert quality.data is not None
    assert quality.data["source_signals"]["dataset_signal_present"] is True
    assert quality.data["issues"] == []
    assert _dataset_status(quality.data, "completeness") == "pass"
    assert _dataset_status(quality.data, "density") == "pass"


def _dataset_status(report: dict, section: str) -> str:
    return next(
        check["status"]
        for check in report[section]["checks"]
        if check["name"] == "datasets_from_availability_signals"
    )


def _write_case(
    folder: Path, statement: str, *, datasets: list[dict[str, str]] | None = None
) -> SourceCase:
    roles = ["objective", "method_claim", "result_claim", "conclusion", "limitation"]
    graph = {
        "id": "csag:synthetic",
        "title": "Synthetic study",
        "schema_version": "1.0.0",
        "validator_version": "1.0.0",
        "assertions": [
            {
                "id": f"csag:assertion/synthetic/A{index}",
                "assertion_text": f"Synthetic {role}.",
                "claim_role": role,
                "normalization_status": "raw",
                "contexts": [{"id": f"csag:context/synthetic/C{index}"}],
                "falsification_criteria": ["The observation does not repeat."],
            }
            for index, role in enumerate(roles)
        ],
        "evidence_items": [
            {"id": "csag:evidence/synthetic/E1", "evidence_type": "observational_data"}
        ],
        "evidence_links": [
            {
                "id": "csag:link/synthetic/L1",
                "evidence_item": "csag:evidence/synthetic/E1",
                "assertion": "csag:assertion/synthetic/A2",
                "polarity": "supports",
            }
        ],
        "datasets": datasets or [],
        "extraction_activities": [
            {
                "id": "csag:activity/synthetic/X1",
                "parameters": [
                    {"key": "doi_status", "value": "unresolved"},
                    {"key": "pmid_status", "value": "unresolved"},
                ],
            }
        ],
    }
    case = SourceCase(
        folder / "graph.json", folder / "source.md", folder / "article.json"
    )
    case.graph.write_text(json.dumps(graph), encoding="utf-8")
    case.source_markdown.write_text(statement + "\n", encoding="utf-8")
    case.article_json.write_text(json.dumps({"abstract": statement}), encoding="utf-8")
    return case
