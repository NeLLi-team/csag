#!/usr/bin/env python3
from __future__ import annotations

import argparse
import filecmp
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = {
    "csag.schema.json": ROOT / "skills/csag-extraction/assets/csag.schema.json",
    "csag.handoff.schema.json": ROOT / "skills/csag-extraction/assets/csag.handoff.schema.json",
    "csag.md": ROOT / "schema/csag.md",
    "README.md": ROOT / "schema/README.md",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify committed generated schema artifacts.")
    parser.add_argument("--update", action="store_true", help="Regenerate committed schema artifacts.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.update:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts/generate_schema_artifacts.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            print(completed.stdout, end="")
            print(completed.stderr, end="", file=sys.stderr)
        return completed.returncode

    mismatches: list[str] = []
    with tempfile.TemporaryDirectory(prefix="csag-schema-artifacts-") as temp_name:
        temp_dir = Path(temp_name)
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts/generate_schema_artifacts.py"), "--out-dir", str(temp_dir)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            print(completed.stdout, end="")
            print(completed.stderr, end="", file=sys.stderr)
            return completed.returncode
        for artifact, committed in ARTIFACTS.items():
            generated = temp_dir / artifact
            if not committed.exists():
                mismatches.append(f"missing committed artifact: {artifact}")
            elif not generated.exists():
                mismatches.append(f"generator did not produce artifact: {artifact}")
            elif not filecmp.cmp(committed, generated, shallow=False):
                mismatches.append(f"stale artifact: {artifact}")

    result = {"ok": not mismatches, "artifacts": list(ARTIFACTS), "mismatches": mismatches}
    print(json.dumps(result, indent=2))
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
