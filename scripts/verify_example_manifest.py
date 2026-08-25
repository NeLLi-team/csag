#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a CSAG example manifest.")
    parser.add_argument("manifest", type=Path)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def example_file(base_dir: Path, value: object) -> Path | None:
    """Return the regular file that value names inside base_dir, else None."""
    if not isinstance(value, str) or not value:
        return None
    path = (base_dir / value).resolve()
    if path.is_file() and base_dir in path.parents:
        return path
    return None


def main() -> int:
    args = parse_args()
    manifest_path = args.manifest.expanduser().resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base_dir = manifest_path.parent

    errors: list[str] = []
    warnings: list[str] = []

    if not manifest.get("id"):
        errors.append("id is missing")
    if not manifest.get("title"):
        errors.append("title is missing")
    if not manifest.get("license"):
        errors.append("license is missing")
    license_url = manifest.get("license_url", "")
    if not license_url.startswith("https://"):
        errors.append("license_url must record an HTTPS license URL")
    license_evidence_url = manifest.get("license_evidence_url", "")
    if not license_evidence_url.startswith(("https://", "local:")):
        errors.append("license_evidence_url must record an HTTPS URL or local evidence path")

    included_outputs = manifest.get("included_outputs", [])
    if not isinstance(included_outputs, list) or not included_outputs:
        errors.append("included_outputs must be a non-empty list")
    else:
        required_outputs = {
            "paper_extraction.json",
            "paper_extraction.validation.json",
            "paper_extraction.quality.json",
        }
        for output in required_outputs:
            if output not in included_outputs:
                errors.append(f"included_outputs missing {output}")
        for output in included_outputs:
            if example_file(base_dir, output) is None:
                errors.append(f"included_outputs path is not a regular file inside the example directory: {output}")
    if not (manifest.get("doi") or manifest.get("pmid") or manifest.get("source_record_url")):
        errors.append("example manifest must record doi, pmid, or source_record_url")
    if not manifest.get("interpretation"):
        errors.append("example manifest must include interpretation")
    if manifest.get("source_pdf"):
        source_path = example_file(base_dir, manifest["source_pdf"])
        if source_path is None:
            errors.append(f"source_pdf is not a regular file inside the example directory: {manifest['source_pdf']}")
        elif len(manifest.get("sha256", "")) != 64:
            errors.append("source_pdf manifests must record a 64-character sha256 digest")
        elif sha256(source_path) != manifest["sha256"]:
            errors.append(f"source_pdf checksum does not match manifest: {source_path}")
    for field in ("included_sources", "included_sidecars"):
        values = manifest.get(field, [])
        if values is None:
            continue
        if not isinstance(values, list):
            errors.append(f"{field} must be a list when present")
            continue
        for value in values:
            if not isinstance(value, str) or not value:
                errors.append(f"{field} contains an invalid path")
            elif example_file(base_dir, value) is None:
                errors.append(f"{field} path is not a regular file inside the example directory: {value}")
    omitted_inputs = manifest.get("omitted_inputs", [])
    if omitted_inputs:
        if not isinstance(omitted_inputs, list):
            errors.append("omitted_inputs must be a list when present")
        else:
            for index, item in enumerate(omitted_inputs):
                prefix = f"omitted_inputs[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{prefix} must be an object")
                    continue
                for field in ("kind", "expected_file", "reason"):
                    if not item.get(field):
                        errors.append(f"{prefix}.{field} is missing")
    else:
        included_sources = manifest.get("included_sources", [])
        included_sidecars = manifest.get("included_sidecars", [])
        if not included_sources or not included_sidecars:
            errors.append(
                "examples without source Markdown and article sidecars must record omitted_inputs"
            )

    if errors:
        print(json.dumps({"ok": False, "manifest": str(manifest_path), "errors": errors, "warnings": warnings}, indent=2))
        return 1
    print(json.dumps({"ok": True, "manifest": str(manifest_path), "warnings": warnings}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
