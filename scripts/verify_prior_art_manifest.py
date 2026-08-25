#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_TOP_LEVEL = {
    "id",
    "status",
    "redistribution_policy",
    "released_fixture_subset",
}

REQUIRED_RELEASED_FIELDS = {
    "slug",
    "topic",
    "example_dir",
    "license",
    "license_url",
    "license_evidence_url",
    "included_files",
    "interpretation",
}

REQUIRED_RELEASED_FILES = {
    "README.md",
    "example_manifest.json",
    "paper_extraction.json",
    "paper_extraction.validation.json",
    "paper_extraction.quality.json",
}


def resolve_manifest_path(manifest_path: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (manifest_path.parent / path).resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the prior-art fixture manifest.")
    parser.add_argument("manifest", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = args.manifest.expanduser().resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    errors: list[str] = []
    missing = REQUIRED_TOP_LEVEL - set(manifest)
    for field in sorted(missing):
        errors.append(f"top-level field missing: {field}")

    if manifest.get("status") != "released":
        errors.append("status must be released; unreviewed papers are cited, not listed")

    released = manifest.get("released_fixture_subset", [])
    released_checked = 0
    if not isinstance(released, list) or not released:
        errors.append("released_fixture_subset must list at least one promoted fixture")
    else:
        seen_released: set[str] = set()
        for index, entry in enumerate(released):
            prefix = f"released_fixture_subset[{index}]"
            if not isinstance(entry, dict):
                errors.append(f"{prefix} must be an object")
                continue
            missing_released_fields = REQUIRED_RELEASED_FIELDS - set(entry)
            for field in sorted(missing_released_fields):
                errors.append(f"{prefix}.{field} is missing")
            slug = entry.get("slug", "")
            if not slug:
                continue
            if slug in seen_released:
                errors.append(f"{prefix}.slug duplicates {slug}")
            seen_released.add(slug)
            if not entry.get("license_url", "").startswith("https://creativecommons.org/"):
                errors.append(f"{prefix}.license_url must be a Creative Commons URL")
            if not entry.get("license_evidence_url", "").startswith("https://"):
                errors.append(f"{prefix}.license_evidence_url must be an HTTPS URL")
            if not entry.get("interpretation", "").strip():
                errors.append(f"{prefix}.interpretation is missing")

            included_files = entry.get("included_files", [])
            if not isinstance(included_files, list) or not included_files:
                errors.append(f"{prefix}.included_files must be a non-empty list")
                included_files = []
            missing_required = REQUIRED_RELEASED_FILES - set(included_files)
            for filename in sorted(missing_required):
                errors.append(f"{prefix}.included_files missing {filename}")

            example_dir_value = entry.get("example_dir", "")
            if example_dir_value:
                example_dir = resolve_manifest_path(manifest_path, example_dir_value)
                if not example_dir.exists():
                    errors.append(f"{prefix}.example_dir does not exist: {example_dir}")
                else:
                    released_checked += 1
                    for filename in included_files:
                        if not isinstance(filename, str) or not filename:
                            errors.append(f"{prefix}.included_files contains an invalid filename")
                            continue
                        if "/" in filename or "\\" in filename:
                            errors.append(f"{prefix}.included_files must contain basenames only: {filename}")
                            continue
                        if not (example_dir / filename).exists():
                            errors.append(f"{prefix}.included_files missing from example_dir: {filename}")

                    markdowns = sorted(example_dir.glob("*.md"))
                    if not [path for path in markdowns if path.name.lower() != "readme.md"]:
                        errors.append(f"{prefix}.example_dir must include converted Markdown")
                    if not list(example_dir.glob("*.section_audit.json")):
                        errors.append(f"{prefix}.example_dir must include a section audit")
                    if not list(example_dir.glob("*.article.json")):
                        errors.append(f"{prefix}.example_dir must include article JSON")

    result = {
        "ok": not errors,
        "manifest": str(manifest_path),
        "released_fixture_count": len(released) if isinstance(released, list) else 0,
        "released_fixture_dirs_checked": released_checked if isinstance(released, list) else 0,
        "errors": errors,
    }
    print(json.dumps(result, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
