"""Source keywords do not impose Dataset counts through the public CSAG APIs."""

import json
from pathlib import Path
from typing import NamedTuple

import pytest

from csag import build_quality_report, validate_extraction

SOURCE_STATEMENTS = [
    "Pride et al. measured viral abundance.",
    "References: Available at https://example.org/article.",
    "Data availability: No datasets were generated or analyzed during this study.",
]


class SourceCase(NamedTuple):
    """Paths to the generated graph and its two independent source forms."""

    graph: Path
    source_markdown: Path
    article_json: Path


@pytest.mark.parametrize("statement", SOURCE_STATEMENTS)
def test_source_keywords_do_not_require_dataset(tmp_path: Path, statement: str) -> None:
    """Dataset coverage requires manuscript review, not keyword counts."""
    case = _write_case(tmp_path, statement)

    validation = validate_extraction(
        case.graph, source_markdown=case.source_markdown, profile="paper_local"
    )

    assert validation.exit_code == 0, validation.stdout + validation.stderr
    assert validation.ok is True
    assert validation.data is not None
    assert validation.data["errors"] == []


@pytest.mark.parametrize("statement", SOURCE_STATEMENTS)
@pytest.mark.parametrize("source_kind", ["source_markdown", "article_json"])
def test_source_keywords_pass_strict_quality(
    tmp_path: Path, statement: str, source_kind: str
) -> None:
    """Keywords do not fail full-article quality in either source format."""
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
    assert quality.data["issues"] == []


@pytest.mark.parametrize(
    ("dataset", "expected_ok"),
    [
        ({"id": "csag:dataset/synthetic/D1", "repository": "Archive"}, True),
        ({"id": "csag:dataset/synthetic/D1", "accession": "SYN001"}, True),
        (
            {
                "id": "csag:dataset/synthetic/D1",
                "dataset_url": "https://example.org/data",
            },
            True,
        ),
        ({"id": "csag:dataset/synthetic/D1"}, True),
        ({"repository": "Archive"}, False),
    ],
)
def test_provided_dataset_is_checked_without_source_keywords(
    tmp_path: Path, dataset: dict[str, str], expected_ok: bool
) -> None:
    """Every supplied Dataset needs an ID; external identifiers are optional."""
    case = _write_case(
        tmp_path,
        "We measured viral abundance.",
        datasets=[dataset],
    )

    validation = validate_extraction(
        case.graph, source_markdown=case.source_markdown, profile="paper_local"
    )
    assert validation.ok is expected_ok, validation.stdout + validation.stderr


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
