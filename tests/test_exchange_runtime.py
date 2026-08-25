from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from pathlib import Path

from csag import build_quality_report, inspect_workdir, lint_extraction, scaffold_extraction, validate_extraction
from csag.paths import ROOT


LITE = ROOT / "examples" / "lite"


def _prepare_lite_workdir(workdir: Path) -> tuple[Path, Path, Path]:
    workdir.mkdir(parents=True)
    markdown = workdir / "paper.md"
    article = workdir / "paper.article.json"
    extraction = workdir / "paper_extraction.json"
    shutil.copy2(LITE / "lite.md", markdown)
    shutil.copy2(LITE / "lite.article.json", article)
    assert scaffold_extraction(markdown, article_json=article, output=extraction, profile="lite").ok
    return markdown, article, extraction


def _write_reports(workdir: Path, markdown: Path, article: Path, extraction: Path) -> None:
    assert validate_extraction(
        extraction,
        source_markdown=markdown,
        article_json=article,
        profile="lite",
        report_out=workdir / "paper_extraction.validation.json",
    ).ok
    assert build_quality_report(
        extraction,
        source_markdown=markdown,
        article_json=article,
        document_scope="lite",
        report_out=workdir / "paper_extraction.quality.json",
    ).ok
    assert lint_extraction(
        extraction,
        report_out=workdir / "paper_extraction.lint.json",
        strict=True,
    ).ok


def test_inspect_detects_source_and_extraction_changes(tmp_path: Path) -> None:
    workdir = tmp_path / "work directory with spaces"
    markdown, article, extraction = _prepare_lite_workdir(workdir)
    _write_reports(workdir, markdown, article, extraction)
    assert inspect_workdir(workdir)["state"] == "complete"

    markdown.write_text(markdown.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    inspected = inspect_workdir(workdir)
    assert inspected["state"] == "validation_stale"
    assert shlex.split(inspected["suggested_next_command"])[2] == str(extraction)

    assert validate_extraction(
        extraction,
        source_markdown=markdown,
        article_json=article,
        profile="lite",
        report_out=workdir / "paper_extraction.validation.json",
    ).ok
    assert inspect_workdir(workdir)["state"] == "quality_stale"

    assert build_quality_report(
        extraction,
        source_markdown=markdown,
        article_json=article,
        document_scope="lite",
        report_out=workdir / "paper_extraction.quality.json",
    ).ok
    assert inspect_workdir(workdir)["state"] == "complete"

    extraction.write_text(extraction.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert inspect_workdir(workdir)["state"] == "validation_stale"


def test_validate_and_report_resolve_relative_paths_from_external_cwd(tmp_path: Path) -> None:
    workdir = tmp_path / "caller cwd"
    markdown, article, extraction = _prepare_lite_workdir(workdir)
    relative = lambda path: str(path.relative_to(workdir))

    validation = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(ROOT),
            "csag",
            "validate",
            relative(extraction),
            "--source-markdown",
            relative(markdown),
            "--article-json",
            relative(article),
            "--profile",
            "lite",
            "--report-out",
            "reports/validation.json",
        ],
        cwd=workdir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert validation.returncode == 0, validation.stdout + validation.stderr

    quality = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(ROOT),
            "csag",
            "report",
            relative(extraction),
            "--source-markdown",
            relative(markdown),
            "--article-json",
            relative(article),
            "--document-scope",
            "lite",
            "--report-out",
            "reports/quality.json",
        ],
        cwd=workdir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert quality.returncode == 0, quality.stdout + quality.stderr

    for report_name in ("validation.json", "quality.json"):
        report_path = workdir / "reports" / report_name
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["inputs"]["extraction"]["path"] == "../paper_extraction.json"
        assert len(report["inputs"]["extraction"]["sha256"]) == 64
        if report_name == "validation.json":
            assert report["extraction_json"] == "../paper_extraction.json"
