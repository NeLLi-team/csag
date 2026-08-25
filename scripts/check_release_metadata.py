#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import yaml

from csag import __version__


ROOT = Path(__file__).resolve().parents[1]


def validator_version() -> str:
    text = (ROOT / "skills/csag-extraction/scripts/validate_paper_extraction.py").read_text(encoding="utf-8")
    match = re.search(r'^VALIDATOR_VERSION\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    return match.group(1) if match else ""


def scaffold_version() -> str:
    text = (ROOT / "csag/scaffold.py").read_text(encoding="utf-8")
    match = re.search(r'^\s*"schema_version"\s*:\s*"([^"]+)"', text, flags=re.MULTILINE)
    return match.group(1) if match else ""


def schema_source_version() -> str:
    schema = yaml.safe_load((ROOT / "skills/csag-extraction/assets/csag.yaml").read_text(encoding="utf-8"))
    return str(schema.get("version") or "")


def extraction_skill_version() -> str:
    text = (ROOT / "skills/csag-extraction/SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", text, flags=re.DOTALL)
    if not match:
        return ""
    frontmatter = yaml.safe_load(match.group(1)) or {}
    return str((frontmatter.get("metadata") or {}).get("version") or "")


def main() -> int:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    zenodo = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))

    versions = {
        "csag.__version__": __version__,
        "pyproject.toml": pyproject["project"]["version"],
        "CITATION.cff": str(citation["version"]),
        ".zenodo.json": str(zenodo["version"]),
        "validate_paper_extraction.py": validator_version(),
        "csag/scaffold.py": scaffold_version(),
        "skills/csag-extraction/SKILL.md": extraction_skill_version(),
        "skills/csag-extraction/assets/csag.yaml": schema_source_version(),
    }
    expected = next(iter(versions.values()))
    mismatches = {name: value for name, value in versions.items() if value != expected}
    text_checks = {
        "README.md": (ROOT / "README.md").read_text(encoding="utf-8"),
        "CHANGELOG.md": (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
    }
    missing_text_mentions = [
        path
        for path, text in text_checks.items()
        if not re.search(rf"\b{re.escape(expected)}\b", text)
    ]
    if mismatches or missing_text_mentions:
        print(
            json.dumps(
                {
                    "ok": False,
                    "version": expected,
                    "versions": versions,
                    "mismatches": mismatches,
                    "missing_text_mentions": missing_text_mentions,
                },
                indent=2,
            )
        )
        return 1

    citation_identifiers = citation.get("identifiers", []) or []
    citation_dois = [
        item.get("value", "")
        for item in citation_identifiers
        if isinstance(item, dict) and item.get("type") == "doi"
    ]
    zenodo_dois = [
        item.get("identifier", "")
        for item in zenodo.get("related_identifiers", []) or []
        if isinstance(item, dict) and item.get("scheme") == "doi"
    ]
    doi_status = {
        "citation_doi": next((doi for doi in citation_dois if doi), ""),
        "zenodo_doi": next((doi for doi in zenodo_dois if doi), ""),
    }
    doi_status["doi_values_match"] = bool(
        doi_status["citation_doi"]
        and doi_status["zenodo_doi"]
        and doi_status["citation_doi"] == doi_status["zenodo_doi"]
    )
    doi_status["archive_doi_recorded"] = doi_status["doi_values_match"] and all(
        value.startswith("10.") and "pending" not in value.lower()
        for value in doi_status.values()
        if isinstance(value, str)
    )

    print(json.dumps({"ok": True, "version": expected, "versions": versions, "doi_status": doi_status}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
