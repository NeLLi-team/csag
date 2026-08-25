#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = ROOT / "tests/fixtures/benchmark"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the benchmark scored-report fixture.")
    parser.add_argument("--update", action="store_true", help="Rewrite the expected scored report.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    expected_path = BENCHMARK_DIR / "scored_report.json"
    invalid_schema = BENCHMARK_DIR / "scoring_schema.invalid_missing_disagreement.json"
    actual_path = BENCHMARK_DIR / ".scored_report.actual.json"
    invalid_report = BENCHMARK_DIR / ".invalid_scored_report.actual.json"
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "csag.cli",
                "score",
                "--answer-key",
                str(BENCHMARK_DIR / "answer_key.hidden.json"),
                "--participant",
                str(BENCHMARK_DIR / "participant_output.json"),
                "--scoring-schema",
                str(BENCHMARK_DIR / "scoring_schema.json"),
                "--report-out",
                str(actual_path),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            print(completed.stdout, end="")
            print(completed.stderr, end="", file=sys.stderr)
            return completed.returncode
        invalid_completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "csag.cli",
                "score",
                "--answer-key",
                str(BENCHMARK_DIR / "answer_key.hidden.json"),
                "--participant",
                str(BENCHMARK_DIR / "participant_output.json"),
                "--scoring-schema",
                str(invalid_schema),
                "--report-out",
                str(invalid_report),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if invalid_completed.returncode == 0:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "reason": "invalid scoring schema unexpectedly passed",
                        "schema": str(invalid_schema),
                    },
                    indent=2,
                )
            )
            return 1
        if "expert_disagreement_note is required" not in invalid_completed.stderr:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "reason": "invalid scoring schema failed for an unexpected reason",
                        "stderr": invalid_completed.stderr,
                    },
                    indent=2,
                )
            )
            return 1
        actual = json.loads(actual_path.read_text(encoding="utf-8"))
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
    finally:
        actual_path.unlink(missing_ok=True)
        invalid_report.unlink(missing_ok=True)

    if actual != expected:
        if args.update:
            expected_path.write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"ok": False, "expected": expected, "actual": actual}, indent=2))
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "report": str(expected_path),
                "positive_scored_report_matches_fixture": True,
                "invalid_schema_rejected": True,
                "invalid_schema": str(invalid_schema),
                "invalid_schema_expected_error": "expert_disagreement_note is required",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
