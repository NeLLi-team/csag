#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_METRIC_EXAMPLES = {
    "examples/toy",
    "examples/lite",
    "examples/pmid35150280",
    "examples/jamy2026",
    "examples/prior-art/ciccarese2013_pav_ontology",
    "examples/prior-art/soilandreyes2022_rocrate",
    "examples/prior-art/stocker2025_machine_readable",
}
REQUIRED_COUNT_FIELDS = {
    "assertions",
    "evidence_links",
    "critiques",
    "knowledge_gaps",
    "artifacts",
    "datasets",
    "qa_items",
}
REQUIRED_COVERAGE_FIELDS = {
    "with_evidence_links",
    "with_decisive_evidence",
    "assertions_with_context",
}
REQUIRED_DISTRIBUTIONS = {
    "criticality",
    "evidence_strength",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify committed example coverage metrics.")
    parser.add_argument("--update", action="store_true", help="Rewrite examples/coverage_metrics.json.")
    return parser.parse_args()


def normalize(report: dict) -> dict:
    normalized = dict(report)
    examples = []
    for row in report.get("examples", []) or []:
        normalized_row = dict(row)
        example = normalized_row.get("example")
        if isinstance(example, str):
            try:
                normalized_row["example"] = str(Path(example).resolve().relative_to(ROOT))
            except ValueError:
                normalized_row["example"] = example
        examples.append(normalized_row)
    normalized["examples"] = examples
    return normalized


def main() -> int:
    args = parse_args()
    expected_path = ROOT / "examples/coverage_metrics.json"
    with tempfile.TemporaryDirectory(prefix="csag-example-metrics-") as temp_name:
        actual_path = Path(temp_name) / "coverage_metrics.json"
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/collect_example_metrics.py"),
                "--examples-dir",
                str(ROOT / "examples"),
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
        actual_raw = json.loads(actual_path.read_text(encoding="utf-8"))
        expected_raw = json.loads(expected_path.read_text(encoding="utf-8"))
        actual = normalize(actual_raw)
        expected = normalize(expected_raw)

    absolute_expected_examples = [
        row.get("example")
        for row in expected_raw.get("examples", []) or []
        if isinstance(row.get("example"), str) and Path(row["example"]).is_absolute()
    ]
    if absolute_expected_examples:
        print(json.dumps({"ok": False, "absolute_example_paths": absolute_expected_examples}, indent=2))
        return 1

    actual_examples = {row.get("example") for row in actual.get("examples", []) or []}
    missing_required = sorted(REQUIRED_METRIC_EXAMPLES - actual_examples)
    if missing_required:
        print(json.dumps({"ok": False, "missing_required_examples": missing_required}, indent=2))
        return 1
    metric_errors: list[str] = []
    for row in actual.get("examples", []) or []:
        example = row.get("example")
        counts = row.get("counts", {})
        coverage = row.get("coverage", {})
        distributions = row.get("distributions", {})
        missing_counts = sorted(REQUIRED_COUNT_FIELDS - set(counts))
        missing_coverage = sorted(REQUIRED_COVERAGE_FIELDS - set(coverage))
        missing_distributions = sorted(REQUIRED_DISTRIBUTIONS - set(distributions))
        if missing_counts:
            metric_errors.append(f"{example}: counts missing {missing_counts}")
        if missing_coverage:
            metric_errors.append(f"{example}: coverage missing {missing_coverage}")
        if missing_distributions:
            metric_errors.append(f"{example}: distributions missing {missing_distributions}")
    if metric_errors:
        print(json.dumps({"ok": False, "metric_errors": metric_errors}, indent=2))
        return 1

    if actual != expected:
        if args.update:
            expected_path.write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"ok": False, "expected": expected, "actual": actual}, indent=2))
        return 1

    print(json.dumps({"ok": True, "report": str(expected_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
