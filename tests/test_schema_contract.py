from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from csag import build_quality_report, inspect_workdir, lint_extraction, scaffold_extraction, validate_extraction
from csag.paths import ROOT
from csag.provenance import check_report_inputs, sha256_file


SCHEMA = json.loads((ROOT / "skills/csag-extraction/assets/csag.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
LITE = ROOT / "examples/lite"


def test_public_examples_conform_to_generated_schema() -> None:
    for path in sorted((ROOT / "examples").glob("**/paper_extraction.json")):
        errors = list(VALIDATOR.iter_errors(json.loads(path.read_text(encoding="utf-8"))))
        assert not errors, f"{path}: {[error.message for error in errors[:5]]}"


def test_closed_schema_rejects_empty_unknown_enum_and_malformed_objects() -> None:
    exemplar = json.loads((LITE / "paper_extraction.json").read_text(encoding="utf-8"))
    assert list(VALIDATOR.iter_errors({}))
    unknown = {**exemplar, "unknown_extension": True}
    assert list(VALIDATOR.iter_errors(unknown))
    exemplar["assertions"][0]["claim_role"] = "invented_role"
    assert list(VALIDATOR.iter_errors(exemplar))
    malformed = json.loads((LITE / "paper_extraction.json").read_text(encoding="utf-8"))
    malformed["assertions"] = ["not-an-object"]
    assert list(VALIDATOR.iter_errors(malformed))


def test_scaffold_passes_both_schema_contracts_and_full_lite_lifecycle(tmp_path: Path) -> None:
    extraction = tmp_path / "paper_extraction.json"
    assert scaffold_extraction(
        LITE / "lite.md",
        article_json=LITE / "lite.article.json",
        output=extraction,
        profile="lite",
    ).ok
    payload = json.loads(extraction.read_text(encoding="utf-8"))
    assert not list(VALIDATOR.iter_errors(payload))

    linkml = subprocess.run(
        [
            "linkml-validate",
            "-s",
            str(ROOT / "skills/csag-extraction/assets/csag.yaml"),
            "-C",
            "PaperExtraction",
            str(extraction),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert linkml.returncode == 0, linkml.stdout + linkml.stderr

    assert validate_extraction(
        extraction,
        source_markdown=LITE / "lite.md",
        article_json=LITE / "lite.article.json",
        profile="lite",
        report_out=tmp_path / "paper_extraction.validation.json",
    ).ok
    assert build_quality_report(
        extraction,
        source_markdown=LITE / "lite.md",
        article_json=LITE / "lite.article.json",
        document_scope="lite",
        report_out=tmp_path / "paper_extraction.quality.json",
    ).ok
    assert lint_extraction(
        extraction,
        report_out=tmp_path / "paper_extraction.lint.json",
        strict=True,
    ).ok
    inspected = inspect_workdir(tmp_path)
    assert inspected["state"] == "complete"
    assert inspected["ready_to_export"] is True


def test_repair_report_certifies_repaired_artifact_not_invalid_source(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "paper_extraction.raw.json"
    repaired = tmp_path / "paper_extraction.repaired.json"
    report_path = tmp_path / "paper_extraction.validation.json"
    payload = json.loads((LITE / "paper_extraction.json").read_text(encoding="utf-8"))
    payload["assertions"][0]["falsification_criteria"] = "A scalar criterion."
    raw.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "skills/csag-extraction/scripts/validate_paper_extraction.py"),
            str(raw),
            "--profile",
            "lite",
            "--repair-out",
            str(repaired),
            "--report-out",
            str(report_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert report["ok"] is True
    assert list(VALIDATOR.iter_errors(payload))
    assert not list(
        VALIDATOR.iter_errors(json.loads(repaired.read_text(encoding="utf-8")))
    )
    assert report["extraction_json"] == repaired.name
    assert report["inputs"]["extraction"]["sha256"] == sha256_file(repaired)
    assert report["inputs"]["source_extraction"]["sha256"] == sha256_file(raw)
    assert check_report_inputs(report_path, report) == (True, [])
