#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests/fixtures/validation_profiles"

FIXTURES = [
    {"name": "lite.valid.json", "profile": "lite"},
    {"name": "lite.invalid_missing_assertion.json", "profile": "lite"},
    {"name": "lite.invalid_missing_context.json", "profile": "lite"},
    {"name": "lite.invalid_missing_evidence_item.json", "profile": "lite"},
    {"name": "lite.invalid_missing_evidence_link.json", "profile": "lite"},
    {"name": "lite.invalid_unresolved_context.json", "profile": "lite"},
    {"name": "paper_local.valid.json", "profile": "paper_local"},
    {"name": "paper_local.invalid_missing_context.json", "profile": "paper_local"},
    {"name": "paper_local.invalid_misplaced_semantics.json", "profile": "paper_local"},
    {
        "name": "paper_local.invalid_missing_dataset.json",
        "profile": "paper_local",
        "source_markdown": "examples/toy/toy.md",
        "article_json": "examples/toy/toy.article.json",
    },
    {
        "name": "paper_local.invalid_missing_artifact.json",
        "profile": "paper_local",
        "article_json": "tests/fixtures/validation_profiles/article_with_figure.json",
    },
    {"name": "promoted_claim.valid.json", "profile": "promoted_claim"},
    {"name": "promoted_claim.invalid_missing_rationale.json", "profile": "promoted_claim"},
    {"name": "promoted_claim.invalid_missing_curation_status.json", "profile": "promoted_claim"},
    {"name": "promoted_claim.invalid_missing_review_provenance.json", "profile": "promoted_claim"},
    {"name": "benchmark_key.valid.json", "profile": "benchmark_key"},
    {"name": "benchmark_key.invalid_weak_core.json", "profile": "benchmark_key"},
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify validation profile expected reports.")
    parser.add_argument("--update", action="store_true", help="Rewrite expected reports from current validator output.")
    return parser.parse_args()


def normalize_report(report: dict) -> dict:
    normalized = dict(report)
    extraction_json = normalized.get("extraction_json")
    if isinstance(extraction_json, str):
        path = Path(extraction_json)
        parts = path.parts
        try:
            start = parts.index("tests")
            normalized["extraction_json"] = str(Path(*parts[start:]))
        except ValueError:
            try:
                normalized["extraction_json"] = str(path.resolve().relative_to(ROOT))
            except ValueError:
                normalized["extraction_json"] = extraction_json
    return normalized


def run_validator(fixture: Path, profile: str, report_out: Path, *, source_markdown: Path | None = None, article_json: Path | None = None) -> int:
    command = [
        sys.executable,
        str(ROOT / "skills/csag-extraction/scripts/validate_paper_extraction.py"),
        str(fixture),
        "--profile",
        profile,
        "--report-out",
        str(report_out),
    ]
    if source_markdown:
        command.extend(["--source-markdown", str(source_markdown)])
    if article_json:
        command.extend(["--article-json", str(article_json)])
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode


def main() -> int:
    args = parse_args()
    mismatches: list[dict] = []
    checked: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="csag-profile-reports-") as temp_name:
        temp_dir = Path(temp_name)
        for fixture_config in FIXTURES:
            fixture_name = fixture_config["name"]
            profile = fixture_config["profile"]
            fixture = FIXTURE_DIR / fixture_name
            expected_path = FIXTURE_DIR / "reports" / fixture_name.replace(".json", ".report.json")
            actual_path = expected_path.with_name(f".{temp_dir.name}.{expected_path.name}.actual")
            source_markdown = ROOT / fixture_config["source_markdown"] if fixture_config.get("source_markdown") else None
            article_json = ROOT / fixture_config["article_json"] if fixture_config.get("article_json") else None
            return_code = run_validator(fixture, profile, actual_path, source_markdown=source_markdown, article_json=article_json)
            actual = normalize_report(json.loads(actual_path.read_text(encoding="utf-8")))
            if not expected_path.exists():
                if args.update:
                    updated = dict(actual)
                    expected_path.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
                    expected = normalize_report(updated)
                else:
                    mismatches.append(
                        {
                            "fixture": fixture_name,
                            "reason": "expected report fixture is missing",
                            "expected_path": str(expected_path),
                        }
                    )
                    expected = {"ok": False}
            else:
                expected = normalize_report(json.loads(expected_path.read_text(encoding="utf-8")))
            expected_ok = bool(expected.get("ok"))
            if (return_code == 0) != expected_ok:
                mismatches.append(
                    {
                        "fixture": fixture_name,
                        "reason": "validator exit code does not match expected ok",
                        "return_code": return_code,
                        "expected_ok": expected_ok,
                    }
                )
            if actual != expected:
                mismatches.append(
                    {
                        "fixture": fixture_name,
                        "reason": "report differs from expected fixture",
                        "expected": expected,
                        "actual": actual,
                    }
                )
                if args.update:
                    updated = dict(actual)
                    expected_path.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
            checked.append({"fixture": fixture_name, "profile": profile, "ok": actual.get("ok")})
            actual_path.unlink(missing_ok=True)

    result = {"ok": not mismatches, "checked": checked, "mismatches": mismatches}
    print(json.dumps(result, indent=2))
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
