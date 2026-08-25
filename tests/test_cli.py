"""Real tests for the csag CLI exercised against bundled fixtures/examples.

Tests invoke the CLI command functions directly (the same entry points
``csag.cli.main`` dispatches to) and write every output under ``tmp_path``.
Paths are anchored on ``csag.cli.ROOT`` so the suite runs from the checkout.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import csag.cli as cli

ROOT = cli.ROOT
TOY_DIR = ROOT / "examples" / "toy"
TOY_EXTRACTION = TOY_DIR / "paper_extraction.json"
TOY_MARKDOWN = TOY_DIR / "toy.md"
TOY_ARTICLE = TOY_DIR / "toy.article.json"
BENCH_DIR = ROOT / "tests" / "fixtures" / "benchmark"
PROFILE_DIR = ROOT / "tests" / "fixtures" / "validation_profiles"


def _read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_validate_toy_paper_local_ok(tmp_path: Path) -> None:
    report_out = tmp_path / "toy.validation.json"
    args = argparse.Namespace(
        extraction_json=TOY_EXTRACTION,
        source_markdown=TOY_MARKDOWN,
        article_json=TOY_ARTICLE,
        profile="paper_local",
        report_out=report_out,
    )
    exit_code = cli.cmd_validate(args)
    report = _read_json(report_out)
    assert exit_code == 0
    assert report["ok"] is True


def test_validate_core_profile_alias_reports_module(tmp_path: Path) -> None:
    report_out = tmp_path / "toy.core.validation.json"
    args = argparse.Namespace(
        extraction_json=TOY_EXTRACTION,
        source_markdown=TOY_MARKDOWN,
        article_json=TOY_ARTICLE,
        profile="core",
        report_out=report_out,
    )
    exit_code = cli.cmd_validate(args)
    report = _read_json(report_out)
    assert exit_code == 0
    assert report["ok"] is True
    assert report["strictness_profile"] == "paper_local"
    assert report["profile_modules"] == ["core"]


def test_validate_module_profile_combination_reports_warnings(tmp_path: Path) -> None:
    report_out = tmp_path / "toy.core_bio.validation.json"
    args = argparse.Namespace(
        extraction_json=TOY_EXTRACTION,
        source_markdown=TOY_MARKDOWN,
        article_json=TOY_ARTICLE,
        profile="core,bio",
        report_out=report_out,
    )
    exit_code = cli.cmd_validate(args)
    report = _read_json(report_out)
    assert exit_code == 0
    assert report["ok"] is True
    assert report["strictness_profile"] == "paper_local"
    assert report["profile_modules"] == ["core", "bio"]
    assert any("profile=bio selected" in warning for warning in report["warnings"])


def test_report_toy_completeness_is_one(tmp_path: Path) -> None:
    report_out = tmp_path / "toy.quality.json"
    args = argparse.Namespace(
        extraction_json=TOY_EXTRACTION,
        source_markdown=TOY_MARKDOWN,
        article_json=TOY_ARTICLE,
        report_out=report_out,
        strict=True,
    )
    exit_code = cli.cmd_report(args)
    report = _read_json(report_out)
    assert exit_code == 0
    assert report["completeness"]["score"] == 1.0


def test_score_benchmark_normalized_score(tmp_path: Path) -> None:
    report_out = tmp_path / "score.json"
    args = argparse.Namespace(
        answer_key=BENCH_DIR / "answer_key.hidden.json",
        participant=BENCH_DIR / "participant_output.json",
        scoring_schema=BENCH_DIR / "scoring_schema.json",
        report_out=report_out,
    )
    exit_code = cli.cmd_score(args)
    report = _read_json(report_out)
    assert exit_code == 0
    assert report["normalized_score"] == 0.75


@pytest.mark.parametrize("export_format", ["jsonld", "graphml", "rdf", "table"])
def test_export_formats_produce_non_empty_file(export_format: str, tmp_path: Path) -> None:
    output = tmp_path / f"toy.{export_format}"
    args = argparse.Namespace(
        extraction_json=TOY_EXTRACTION,
        format=export_format,
        output=output,
    )
    exit_code = cli.cmd_export(args)
    assert exit_code == 0
    assert output.exists()
    assert output.stat().st_size > 0


# Validation-profile fixtures keyed to the profile they exercise. Two
# paper_local "invalid" fixtures only violate their invariant when the source
# signals (markdown / article json) are supplied; that mapping mirrors
# scripts/check_validation_profile_reports.py.
_PROFILE_CASES = [
    ("paper_local.valid.json", "paper_local", True, {}),
    ("paper_local.invalid_missing_context.json", "paper_local", False, {}),
    ("paper_local.invalid_misplaced_semantics.json", "paper_local", False, {}),
    (
        "paper_local.invalid_missing_dataset.json",
        "paper_local",
        False,
        {"source_markdown": TOY_MARKDOWN, "article_json": TOY_ARTICLE},
    ),
    (
        "paper_local.invalid_missing_artifact.json",
        "paper_local",
        False,
        {"article_json": PROFILE_DIR / "article_with_figure.json"},
    ),
    ("promoted_claim.valid.json", "promoted_claim", True, {}),
    ("promoted_claim.invalid_missing_rationale.json", "promoted_claim", False, {}),
    ("promoted_claim.invalid_missing_curation_status.json", "promoted_claim", False, {}),
    ("promoted_claim.invalid_missing_review_provenance.json", "promoted_claim", False, {}),
    ("benchmark_key.valid.json", "benchmark_key", True, {}),
    ("benchmark_key.invalid_weak_core.json", "benchmark_key", False, {}),
]


@pytest.mark.parametrize(
    ("fixture_name", "profile", "expect_ok", "extra"),
    _PROFILE_CASES,
    ids=[case[0] for case in _PROFILE_CASES],
)
def test_validation_profile_fixtures(
    fixture_name: str,
    profile: str,
    expect_ok: bool,
    extra: dict,
    tmp_path: Path,
) -> None:
    fixture = PROFILE_DIR / fixture_name
    assert fixture.exists(), f"missing fixture: {fixture}"
    report_out = tmp_path / f"{fixture_name}.report.json"
    args = argparse.Namespace(
        extraction_json=fixture,
        source_markdown=extra.get("source_markdown"),
        article_json=extra.get("article_json"),
        profile=profile,
        report_out=report_out,
    )
    exit_code = cli.cmd_validate(args)
    report = _read_json(report_out)
    assert report["ok"] is expect_ok
    assert (exit_code == 0) is expect_ok
