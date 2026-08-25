from __future__ import annotations

import json
from pathlib import Path

import csag.cli as cli
from csag import (
    build_quality_report,
    export_extraction,
    inspect_workdir,
    lint_extraction,
    scaffold_extraction,
    validate_extraction,
)
from csag.provenance import input_records

ROOT = cli.ROOT
TOY = ROOT / "examples" / "toy" / "paper_extraction.json"
TOY_MD = ROOT / "examples" / "toy" / "toy.md"
TOY_ARTICLE = ROOT / "examples" / "toy" / "toy.article.json"


def test_public_api_imports() -> None:
    from csag import (  # noqa: F401
        ingest_manuscript,
        scaffold_extraction,
        inspect_workdir,
        validate_extraction,
        build_quality_report,
        lint_extraction,
        export_extraction,
    )


def test_validate_and_report_api_parse_json(tmp_path: Path) -> None:
    validation = validate_extraction(TOY, source_markdown=TOY_MD, article_json=TOY_ARTICLE, profile="lite")
    assert validation.ok
    assert validation.data and validation.data["profile"] == "lite"
    quality = build_quality_report(TOY, source_markdown=TOY_MD, article_json=TOY_ARTICLE, document_scope="lite")
    assert quality.ok
    assert quality.data and quality.data["density"]["document_scope"] == "lite"


def test_scaffold_ignores_reference_only_doi(tmp_path: Path) -> None:
    md = tmp_path / "paper.md"
    md.write_text(
        "# A Study With No Own DOI\n\nBlue light increased pigment.\n\n"
        "## References\n\n1. Someone. Cited paper. https://doi.org/10.1234/ref.doi\n",
        encoding="utf-8",
    )
    output = tmp_path / "paper_extraction.json"
    assert scaffold_extraction(md, output=output, profile="lite").ok
    extraction = json.loads(output.read_text(encoding="utf-8"))
    assert extraction["id"].startswith("csag:doc/")
    assert "10.1234/ref.doi" not in extraction["id"]


def test_inspect_reports_lint_failure(tmp_path: Path) -> None:
    extraction = tmp_path / "paper_extraction.json"
    extraction.write_text("{}", encoding="utf-8")
    inputs = input_records(base_dir=tmp_path, extraction=extraction)
    (tmp_path / "paper_extraction.validation.json").write_text(
        json.dumps({"ok": True, "inputs": inputs}), encoding="utf-8"
    )
    (tmp_path / "paper_extraction.quality.json").write_text(
        json.dumps({"issues": [], "inputs": inputs}), encoding="utf-8"
    )
    (tmp_path / "paper_extraction.lint.json").write_text(
        json.dumps({"ok": False, "inputs": inputs}), encoding="utf-8"
    )
    inspected = inspect_workdir(tmp_path)
    assert inspected["state"] == "lint_failed"
    assert inspected["ready_to_export"] is False


def test_scaffold_inspect_lint_export_api(tmp_path: Path) -> None:
    output = tmp_path / "paper_extraction.json"
    result = scaffold_extraction(TOY_MD, article_json=TOY_ARTICLE, output=output, profile="lite")
    assert result.ok and output.exists()
    inspected = inspect_workdir(tmp_path)
    assert inspected["state"] == "scaffolded_or_curated"
    validation = validate_extraction(output, profile="lite", report_out=tmp_path / "paper_extraction.validation.json")
    assert validation.ok
    lint = lint_extraction(output, report_out=tmp_path / "paper_extraction.lint.json", strict=False)
    assert lint.ok
    exported = export_extraction(output, format="table", output=tmp_path / "out.tsv")
    assert exported.ok
    assert (tmp_path / "out.tsv").exists()
