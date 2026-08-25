from __future__ import annotations

import argparse
import json
from pathlib import Path

import csag.cli as cli

ROOT = cli.ROOT
TOY = ROOT / "examples" / "toy" / "paper_extraction.json"
TOY_MD = ROOT / "examples" / "toy" / "toy.md"
TOY_ARTICLE = ROOT / "examples" / "toy" / "toy.article.json"
LITE = ROOT / "examples" / "lite" / "paper_extraction.json"
LITE_MD = ROOT / "examples" / "lite" / "lite.md"
LITE_ARTICLE = ROOT / "examples" / "lite" / "lite.article.json"


def _report(path: Path, markdown: Path, article: Path, scope: str, tmp_path: Path, strict: bool = False) -> tuple[int, dict]:
    out = tmp_path / f"{scope}.json"
    args = argparse.Namespace(extraction_json=path, source_markdown=markdown, article_json=article, report_out=out, strict=strict, document_scope=scope)
    code = cli.cmd_report(args)
    return code, json.loads(out.read_text(encoding="utf-8"))


def test_lite_scope_passes_small_example(tmp_path: Path) -> None:
    code, report = _report(LITE, LITE_MD, LITE_ARTICLE, "lite", tmp_path, strict=True)
    assert code == 0
    assert report["density"]["document_scope"] == "lite"
    assert all(item["status"] == "pass" for item in report["density"]["checks"])


def test_lite_scope_ignores_full_article_artifact_dataset_expectations(tmp_path: Path) -> None:
    article = json.loads(LITE_ARTICLE.read_text(encoding="utf-8"))
    article["figure_legends"] = ["Figure 1. Pigment response under blue light."]
    article["data_availability"] = "Data availability: raw reads are available from the SRA repository."
    article_path = tmp_path / "lite_with_full_article_signals.article.json"
    article_path.write_text(json.dumps(article, indent=2) + "\n", encoding="utf-8")

    code, report = _report(LITE, LITE_MD, article_path, "lite", tmp_path, strict=True)
    check_names = {item["name"] for item in report["completeness"]["checks"]}

    assert code == 0
    assert report["source_signals"]["figure_or_table_caption_present"] is True
    assert report["source_signals"]["dataset_signal_present"] is True
    assert "artifacts_from_captions" not in check_names
    assert "datasets_from_availability_signals" not in check_names


def test_sparse_full_article_warns_by_default_and_fails_strict(tmp_path: Path) -> None:
    code, report = _report(TOY, TOY_MD, TOY_ARTICLE, "full_article", tmp_path, strict=False)
    assert code == 0
    assert any(item["name"] == "full_article_assertions" and item["status"] == "warn" for item in report["density"]["checks"])
    strict_code, strict_report = _report(TOY, TOY_MD, TOY_ARTICLE, "full_article", tmp_path, strict=True)
    assert strict_code == 1
    assert strict_report["issues"]
