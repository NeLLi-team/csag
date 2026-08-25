#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import json
import subprocess
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
LINKML_SCHEMA = ROOT / "skills/csag-extraction/assets/csag.yaml"
JSON_SCHEMA = ROOT / "skills/csag-extraction/assets/csag.schema.json"
HANDOFF_JSON_SCHEMA = ROOT / "skills/csag-extraction/assets/csag.handoff.schema.json"
HANDOFF_FIXTURE = ROOT / "tests/fixtures/handoff/two_agent_handoff.valid.json"


def candidate_paths() -> list[Path]:
    paths = sorted((ROOT / "examples").glob("**/paper_extraction.json"))
    profile_dir = ROOT / "tests/fixtures/validation_profiles"
    paths.extend(profile_dir / name for name in (
        "lite.valid.json",
        "paper_local.valid.json",
        "promoted_claim.valid.json",
        "benchmark_key.valid.json",
    ))
    benchmark_dir = ROOT / "tests/fixtures/benchmark"
    paths.extend((benchmark_dir / "answer_key.hidden.json", benchmark_dir / "participant_output.json"))
    return paths


def main() -> int:
    schema = json.loads(JSON_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    failures: list[dict[str, object]] = []

    for path in candidate_paths():
        payload = json.loads(path.read_text(encoding="utf-8"))
        errors = list(validator.iter_errors(payload))
        if errors:
            failures.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "validator": "jsonschema",
                    "errors": [error.message for error in errors[:10]],
                }
            )
        linkml = subprocess.run(
            [
                "linkml-validate",
                "-s",
                str(LINKML_SCHEMA),
                "-C",
                "PaperExtraction",
                str(path),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if linkml.returncode:
            failures.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "validator": "linkml",
                    "errors": (linkml.stdout + linkml.stderr).splitlines()[:10],
                }
            )

    handoff_schema = json.loads(HANDOFF_JSON_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(handoff_schema)
    handoff_validator = Draft202012Validator(handoff_schema, format_checker=FormatChecker())
    handoff_payload = json.loads(HANDOFF_FIXTURE.read_text(encoding="utf-8"))
    handoff_errors = list(handoff_validator.iter_errors(handoff_payload))
    if handoff_errors:
        failures.append(
            {
                "path": str(HANDOFF_FIXTURE.relative_to(ROOT)),
                "validator": "jsonschema:HandoffEnvelope",
                "errors": [error.message for error in handoff_errors[:10]],
            }
        )
    handoff_linkml = subprocess.run(
        [
            "linkml-validate",
            "-s",
            str(LINKML_SCHEMA),
            "-C",
            "HandoffEnvelope",
            str(HANDOFF_FIXTURE),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if handoff_linkml.returncode:
        failures.append(
            {
                "path": str(HANDOFF_FIXTURE.relative_to(ROOT)),
                "validator": "linkml:HandoffEnvelope",
                "errors": (handoff_linkml.stdout + handoff_linkml.stderr).splitlines()[:10],
            }
        )
    exemplar = json.loads((ROOT / "examples/lite/paper_extraction.json").read_text(encoding="utf-8"))
    negative_cases = {
        "empty_object": {},
        "unknown_root_field": {**exemplar, "unknown_extension": True},
        "invalid_claim_role": deepcopy(exemplar),
        "malformed_assertion": {**exemplar, "assertions": ["not-an-object"]},
    }
    negative_cases["invalid_claim_role"]["assertions"][0]["claim_role"] = "invented_role"
    negative_failures = [name for name, payload in negative_cases.items() if not list(validator.iter_errors(payload))]
    if negative_failures:
        failures.append(
            {
                "path": "synthetic-negative-cases",
                "validator": "jsonschema",
                "errors": [f"unexpectedly accepted: {name}" for name in negative_failures],
            }
        )

    result = {
        "ok": not failures,
        "linkml_schema": str(LINKML_SCHEMA.relative_to(ROOT)),
        "json_schema": str(JSON_SCHEMA.relative_to(ROOT)),
        "validated_artifacts": len(candidate_paths()) + 1,
        "negative_cases": sorted(negative_cases),
        "failures": failures,
    }
    print(json.dumps(result, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
