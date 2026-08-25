from __future__ import annotations

import hashlib
import os
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_record(path: Path, *, base_dir: Path) -> dict[str, object]:
    resolved = path.expanduser().resolve()
    return {
        "path": os.path.relpath(resolved, base_dir.expanduser().resolve()),
        "sha256": sha256_file(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def input_records(*, base_dir: Path, **paths: Path | None) -> dict[str, dict[str, object]]:
    return {
        name: input_record(path, base_dir=base_dir)
        for name, path in paths.items()
        if path is not None
    }


def check_report_inputs(report_path: Path, report: dict) -> tuple[bool, list[dict[str, str]]]:
    inputs = report.get("inputs")
    if not isinstance(inputs, dict) or not inputs:
        return False, [{"input": "(report)", "reason": "missing input hashes"}]
    stale: list[dict[str, str]] = []
    for name, record in inputs.items():
        if not isinstance(record, dict) or not isinstance(record.get("path"), str) or not isinstance(record.get("sha256"), str):
            stale.append({"input": str(name), "reason": "invalid input record"})
            continue
        path = Path(record["path"])
        if not path.is_absolute():
            path = report_path.parent / path
        path = path.expanduser().resolve()
        if not path.exists():
            stale.append({"input": str(name), "reason": "input is missing", "path": str(path)})
        elif not path.is_file():
            stale.append({"input": str(name), "reason": "input is not a regular file", "path": str(path)})
        elif sha256_file(path) != record["sha256"]:
            stale.append({"input": str(name), "reason": "SHA-256 differs", "path": str(path)})
    return not stale, stale
