#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect CSAG coverage metrics across example quality reports.")
    parser.add_argument("--examples-dir", type=Path, default=Path("examples"))
    parser.add_argument("--report-out", type=Path, default=Path("examples/coverage_metrics.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    examples_dir = args.examples_dir.expanduser().resolve()
    display_root = examples_dir.parent
    rows: list[dict] = []
    for quality_path in sorted(examples_dir.glob("**/paper_extraction.quality.json")):
        report = json.loads(quality_path.read_text(encoding="utf-8"))
        example_dir = quality_path.parent.resolve()
        try:
            example = str(example_dir.relative_to(display_root))
        except ValueError:
            example = str(example_dir)
        rows.append(
            {
                "example": example,
                "extraction_id": report.get("extraction_id"),
                "counts": report.get("counts", {}),
                "coverage": report.get("coverage", {}),
                "distributions": report.get("distributions", {}),
                "grounding": report.get("grounding", {}),
                "issues": report.get("issues", []),
            }
        )
    summary = {
        "example_count": len(rows),
        "examples": rows,
    }
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(args.report_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
