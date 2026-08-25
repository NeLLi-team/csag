from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from jsonschema import Draft202012Validator, FormatChecker

import csag.cli as cli
from csag import validate_extraction
from csag.paths import ROOT
from csag.provenance import check_report_inputs, sha256_file


SCHEMA_YAML = ROOT / "skills/csag-extraction/assets/csag.yaml"
HANDOFF_SCHEMA = json.loads((ROOT / "skills/csag-extraction/assets/csag.handoff.schema.json").read_text(encoding="utf-8"))
PAPER_SCHEMA = json.loads((ROOT / "skills/csag-extraction/assets/csag.schema.json").read_text(encoding="utf-8"))
HANDOFF_FIXTURE = ROOT / "tests/fixtures/handoff/two_agent_handoff.valid.json"
SOURCE_SNAPSHOT = ROOT / "tests/fixtures/handoff/source_snapshot.paper_extraction.json"
HANDOFF_VALIDATOR = ROOT / "skills/csag-extraction/scripts/validate_handoff_envelope.py"
FIXTURE_LOCAL_FILES = (
    "source_snapshot.paper_extraction.json",
    "source_snapshot.md",
    "source_snapshot.article.json",
    "source_snapshot.validation.json",
    "source_snapshot.quality.json",
    "environment.lock",
)


def read_fixture() -> dict:
    return json.loads(HANDOFF_FIXTURE.read_text(encoding="utf-8"))


def run_custom_validator(
    payload: dict,
    tmp_path: Path,
    file_overrides: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    envelope = tmp_path / "handoff.json"
    report = tmp_path / "handoff.validation.json"
    envelope.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for name in FIXTURE_LOCAL_FILES:
        shutil.copy2(HANDOFF_FIXTURE.parent / name, tmp_path / name)
    for name, content in (file_overrides or {}).items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(HANDOFF_VALIDATOR),
            str(envelope),
            "--profile",
            "handoff",
            "--report-out",
            str(report),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed, json.loads(report.read_text(encoding="utf-8"))


def update_artifact_identity(payload: dict, artifact_path: str, content: str) -> None:
    encoded = content.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    matches = 0
    artifacts = [
        *payload["source_artifacts"],
        *(item for execution in payload["executions"] for item in execution["inputs"]),
        *(item for execution in payload["executions"] for item in execution["outputs"]),
    ]
    for artifact in artifacts:
        if artifact["artifact_path"] == artifact_path:
            artifact["sha256"] = digest
            artifact["byte_size"] = len(encoded)
            matches += 1
    assert matches > 0


def test_two_agent_fixture_passes_json_schema_linkml_and_handoff_profile(tmp_path: Path) -> None:
    payload = read_fixture()
    json_schema = Draft202012Validator(HANDOFF_SCHEMA, format_checker=FormatChecker())
    assert not list(json_schema.iter_errors(payload))

    linkml = subprocess.run(
        [
            "linkml-validate",
            "-s",
            str(SCHEMA_YAML),
            "-C",
            "HandoffEnvelope",
            str(HANDOFF_FIXTURE),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert linkml.returncode == 0, linkml.stdout + linkml.stderr

    completed, report = run_custom_validator(payload, tmp_path)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert report["ok"] is True
    assert report["profile"] == "handoff"
    assert report["envelope_json"] == "handoff.json"
    assert report["inputs"]["envelope_json"]["path"] == "handoff.json"
    assert {record["path"] for record in report["inputs"].values()} == {
        "handoff.json",
        *FIXTURE_LOCAL_FILES,
    }
    assert report["metrics"] == {
        "source_artifacts": 3,
        "assessments": 2,
        "actions": 2,
        "executions": 2,
        "conflicts": 1,
        "current_heads": 1,
    }


def test_paper_and_handoff_roots_remain_separate() -> None:
    paper = json.loads((ROOT / "examples/lite/paper_extraction.json").read_text(encoding="utf-8"))
    handoff = read_fixture()
    paper_validator = Draft202012Validator(PAPER_SCHEMA, format_checker=FormatChecker())
    handoff_validator = Draft202012Validator(HANDOFF_SCHEMA, format_checker=FormatChecker())
    assert not list(paper_validator.iter_errors(paper))
    assert list(paper_validator.iter_errors(handoff))
    assert list(handoff_validator.iter_errors(paper))


def test_worked_fixture_declares_exact_hash_and_size_for_every_local_file() -> None:
    payload = read_fixture()
    artifacts = [
        *payload["source_artifacts"],
        *(item for execution in payload["executions"] for item in execution["inputs"]),
        *(item for execution in payload["executions"] for item in execution["outputs"]),
    ]
    assert {artifact["artifact_path"] for artifact in artifacts} == {
        name for name in FIXTURE_LOCAL_FILES if name != "environment.lock"
    }
    for artifact in artifacts:
        path = HANDOFF_FIXTURE.parent / artifact["artifact_path"]
        assert path.is_file()
        assert sha256_file(path) == artifact["sha256"]
        assert path.stat().st_size == artifact["byte_size"]

    for execution in payload["executions"]:
        environment_path, declared_digest = execution["environment"].rsplit("#sha256=", 1)
        path = HANDOFF_FIXTURE.parent / environment_path
        assert path.is_file()
        assert sha256_file(path) == declared_digest

    for name in ("source_snapshot.validation.json", "source_snapshot.quality.json"):
        report_path = HANDOFF_FIXTURE.parent / name
        fresh, stale_inputs = check_report_inputs(
            report_path,
            json.loads(report_path.read_text(encoding="utf-8")),
        )
        assert fresh is True, stale_inputs


def test_closed_handoff_schema_rejects_unknown_fields_and_bad_digests() -> None:
    validator = Draft202012Validator(HANDOFF_SCHEMA, format_checker=FormatChecker())
    unknown = read_fixture()
    unknown["implicit_merge"] = True
    assert list(validator.iter_errors(unknown))

    bad_digest = read_fixture()
    bad_digest["source_artifacts"][0]["sha256"] = "not-a-sha256"
    assert list(validator.iter_errors(bad_digest))

    bad_version = read_fixture()
    bad_version["envelope_version"] = "2.0.0"
    assert list(validator.iter_errors(bad_version))


def test_normal_validate_cli_routes_handoff_profile(tmp_path: Path) -> None:
    envelope = tmp_path / "handoff.json"
    report = tmp_path / "handoff.validation.json"
    envelope.write_text(HANDOFF_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    for name in FIXTURE_LOCAL_FILES:
        shutil.copy2(HANDOFF_FIXTURE.parent / name, tmp_path / name)
    code = cli.main(
        [
            "validate",
            str(envelope),
            "--profile",
            "handoff",
            "--report-out",
            str(report),
        ]
    )
    assert code == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["profile"] == "handoff"


def test_python_validation_api_routes_handoff_profile(tmp_path: Path) -> None:
    result = validate_extraction(
        HANDOFF_FIXTURE,
        profile="handoff",
        report_out=tmp_path / "handoff.validation.json",
    )
    assert result.ok is True
    assert result.exit_code == 0
    assert result.data["profile"] == "handoff"
    assert "artifact_001" in result.data["inputs"]


def test_handoff_profile_rejects_dangling_dependencies_and_execution_links(tmp_path: Path) -> None:
    payload = read_fixture()
    payload["actions"][1]["dependencies"] = ["csag:handoff/action/missing"]
    payload["executions"][0]["action_ref"] = "csag:handoff/action/missing"
    completed, report = run_custom_validator(payload, tmp_path)
    assert completed.returncode == 1
    assert report["ok"] is False
    assert any("dependencies" in error and "does not resolve" in error for error in report["errors"])
    assert any("action_ref" in error and "does not resolve" in error for error in report["errors"])


def test_handoff_profile_rejects_unbased_assessments_and_incomplete_completed_runs(tmp_path: Path) -> None:
    payload = read_fixture()
    for field in ("basis_artifacts", "basis_refs", "basis_executions"):
        payload["assessments"][0].pop(field, None)
    payload["executions"][0].pop("outputs")
    payload["executions"][0].pop("execution_outcome")
    completed, report = run_custom_validator(payload, tmp_path)
    assert completed.returncode == 1
    assert any("assessment requires at least one" in error for error in report["errors"])
    assert any("completed execution requires at least one" in error for error in report["errors"])
    assert any("completed execution requires an outcome" in error for error in report["errors"])


def test_handoff_profile_rejects_duplicate_ids_cycles_and_bad_conflict_heads(tmp_path: Path) -> None:
    payload = read_fixture()
    payload["actions"][1]["id"] = payload["actions"][0]["id"]
    payload["actions"][0]["dependencies"] = [payload["actions"][0]["id"]]
    payload["conflicts"][0]["resolved_by_head"] = payload["parents"][0]
    completed, report = run_custom_validator(payload, tmp_path)
    assert completed.returncode == 1
    assert any("duplicate object ID" in error for error in report["errors"])
    assert any("cannot depend on itself" in error for error in report["errors"])
    assert any("dependency cycle" in error for error in report["errors"])
    assert any("must point to a current head" in error for error in report["errors"])


def test_handoff_profile_accepts_open_conflict_with_all_competing_heads_current(
    tmp_path: Path,
) -> None:
    payload = read_fixture()
    conflict = payload["conflicts"][0]
    conflict["conflict_status"] = "open"
    conflict.pop("resolution")
    conflict.pop("resolved_by_head")
    payload["current_heads"] = list(conflict["competing_heads"])
    completed, report = run_custom_validator(payload, tmp_path)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert report["ok"] is True


def test_handoff_profile_rejects_resolution_fields_on_open_conflict(
    tmp_path: Path,
) -> None:
    payload = read_fixture()
    conflict = payload["conflicts"][0]
    conflict["conflict_status"] = "open"
    payload["current_heads"] = list(conflict["competing_heads"])
    completed, report = run_custom_validator(payload, tmp_path)
    assert completed.returncode == 1
    assert any(
        "open conflict cannot record a resolution" in error
        for error in report["errors"]
    )


def test_handoff_profile_rejects_noncurrent_open_conflict_head(
    tmp_path: Path,
) -> None:
    payload = read_fixture()
    conflict = payload["conflicts"][0]
    conflict["conflict_status"] = "open"
    conflict.pop("resolution")
    conflict.pop("resolved_by_head")
    payload["current_heads"] = [conflict["competing_heads"][0]]
    completed, report = run_custom_validator(payload, tmp_path)
    assert completed.returncode == 1
    assert any(
        "open conflict heads must be current" in error
        for error in report["errors"]
    )


def test_handoff_profile_rejects_inconsistent_content_identity(tmp_path: Path) -> None:
    payload = deepcopy(read_fixture())
    payload["executions"][0]["inputs"][0]["sha256"] = "0" * 64
    completed, report = run_custom_validator(payload, tmp_path)
    assert completed.returncode == 1
    assert any("inconsistent hashes or sizes" in error for error in report["errors"])


def test_handoff_profile_rejects_consistent_digest_that_disagrees_with_local_bytes(tmp_path: Path) -> None:
    payload = read_fixture()
    for artifact in [
        *payload["source_artifacts"],
        *(item for execution in payload["executions"] for item in execution["inputs"]),
        *(item for execution in payload["executions"] for item in execution["outputs"]),
    ]:
        if artifact["artifact_path"] == "source_snapshot.paper_extraction.json":
            artifact["sha256"] = "0" * 64
    completed, report = run_custom_validator(payload, tmp_path)
    assert completed.returncode == 1
    assert not any("inconsistent hashes or sizes" in error for error in report["errors"])
    assert sum("digest does not match local artifact bytes" in error for error in report["errors"]) == 3


def test_handoff_profile_rejects_forged_environment_lock_digest(tmp_path: Path) -> None:
    payload = read_fixture()
    for execution in payload["executions"]:
        execution["environment"] = "environment.lock#sha256=" + "0" * 64
    completed, report = run_custom_validator(payload, tmp_path)
    assert completed.returncode == 1
    assert sum("digest does not match local environment lockfile" in error for error in report["errors"]) == 2


def test_handoff_profile_resolves_source_object_references(tmp_path: Path) -> None:
    payload = read_fixture()
    payload["assessments"][0]["basis_refs"] = ["csag:evidence/missing"]
    payload["actions"][0]["target_assertions"] = ["csag:assertion/missing"]
    payload["actions"][1]["target_knowledge_gaps"] = ["csag:gap/missing"]
    completed, report = run_custom_validator(payload, tmp_path)
    assert completed.returncode == 1
    assert any("basis_refs" in error and "does not resolve" in error for error in report["errors"])
    assert any("target_assertions" in error and "does not resolve" in error for error in report["errors"])
    assert any("target_knowledge_gaps" in error and "does not resolve" in error for error in report["errors"])


def test_handoff_profile_rejects_missing_relative_artifact(tmp_path: Path) -> None:
    payload = read_fixture()
    payload["source_artifacts"][0]["artifact_path"] = "missing.paper_extraction.json"
    payload["executions"][0]["inputs"][0]["artifact_path"] = "missing.paper_extraction.json"
    completed, report = run_custom_validator(payload, tmp_path)
    assert completed.returncode == 1
    assert any("local artifact does not exist" in error for error in report["errors"])


def test_handoff_profile_rejects_bundle_path_traversal(tmp_path: Path) -> None:
    payload = read_fixture()
    payload["source_artifacts"][1]["artifact_path"] = "../outside.md"
    completed, report = run_custom_validator(payload, tmp_path)
    assert completed.returncode == 1
    assert any("escapes the handoff bundle" in error for error in report["errors"])


def test_handoff_profile_rejects_absolute_local_path(tmp_path: Path) -> None:
    payload = read_fixture()
    payload["source_artifacts"][1]["artifact_path"] = str(
        (tmp_path.parent / "outside.md").resolve()
    )
    completed, report = run_custom_validator(payload, tmp_path)
    assert completed.returncode == 1
    assert any("absolute local paths are not allowed" in error for error in report["errors"])


def test_handoff_profile_rejects_malformed_source_and_stale_reports(
    tmp_path: Path,
) -> None:
    payload = read_fixture()
    source_content = "{}\n"
    update_artifact_identity(
        payload,
        "source_snapshot.paper_extraction.json",
        source_content,
    )
    completed, report = run_custom_validator(
        payload,
        tmp_path,
        {"source_snapshot.paper_extraction.json": source_content},
    )
    assert completed.returncode == 1
    assert any("violates the closed schema" in error for error in report["errors"])
    assert any("stale or invalid inputs" in error for error in report["errors"])
    assert any("requires a fresh successful validation_report" in error for error in report["errors"])


def test_handoff_profile_rejects_stale_reports_after_valid_source_change(
    tmp_path: Path,
) -> None:
    payload = read_fixture()
    source = json.loads(SOURCE_SNAPSHOT.read_text(encoding="utf-8"))
    source["title"] += " revised"
    source_content = json.dumps(source, indent=2) + "\n"
    update_artifact_identity(
        payload,
        "source_snapshot.paper_extraction.json",
        source_content,
    )
    completed, report = run_custom_validator(
        payload,
        tmp_path,
        {"source_snapshot.paper_extraction.json": source_content},
    )
    assert completed.returncode == 1
    assert not any("violates the closed schema" in error for error in report["errors"])
    assert any("validation_report has stale or invalid inputs" in error for error in report["errors"])
    assert any("quality_report has stale or invalid inputs" in error for error in report["errors"])
