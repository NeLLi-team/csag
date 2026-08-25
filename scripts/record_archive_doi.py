#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
RELEASE_TAG = f"v{PROJECT_VERSION}"
PLACEHOLDER_NOTE = " (placeholder until the release is archived)"
DOI_PATTERN = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record the archive DOI in release metadata."
    )
    parser.add_argument("doi", help="Archive DOI, for example 10.5281/zenodo.1234567.")
    parser.add_argument("--repo", default="NeLLi-team/csag", help="GitHub repository for release-note updates.")
    parser.add_argument("--tag", default=RELEASE_TAG, help="GitHub release tag to update.")
    parser.add_argument(
        "--update-github-release",
        action="store_true",
        help="Append or replace the archive DOI in the GitHub release notes using gh.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate inputs and report planned changes without writing files.",
    )
    return parser.parse_args()


def normalize_doi(raw: str) -> str:
    doi = raw.strip()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
    if not DOI_PATTERN.fullmatch(doi):
        raise ValueError(f"Invalid DOI: {raw!r}")
    return doi


def update_citation(path: Path, doi: str, *, write: bool) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines()
    changed = False
    in_doi_identifier = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "- type: doi":
            in_doi_identifier = True
            continue
        if in_doi_identifier and stripped.startswith("value:"):
            new_line = re.sub(r'value:\s*".*"', f'value: "{doi}"', line)
            if new_line != line:
                lines[index] = new_line
                changed = True
            in_doi_identifier = False
            continue
        if "pending-zenodo-doi" in line:
            new_line = line.replace("pending-zenodo-doi", doi)
            if new_line != line:
                lines[index] = new_line
                changed = True
        if PLACEHOLDER_NOTE in line:
            lines[index] = line.replace(PLACEHOLDER_NOTE, f" for the {RELEASE_TAG} release")
            changed = True
    if changed and write:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changed


def update_zenodo(path: Path, doi: str, *, write: bool) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    related = data.setdefault("related_identifiers", [])
    target = None
    for item in related:
        if item.get("scheme") == "doi" and item.get("relation") == "isIdenticalTo":
            target = item
            break
    if target is None:
        target = {"identifier": doi, "relation": "isIdenticalTo", "scheme": "doi"}
        related.append(target)
        changed = True
    else:
        changed = target.get("identifier") != doi
        target["identifier"] = doi
    if changed and write:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return changed


def update_github_release(repo: str, tag: str, doi: str, *, write: bool) -> bool:
    view = subprocess.run(
        ["gh", "release", "view", tag, "--repo", repo, "--json", "body"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    body = json.loads(view.stdout).get("body", "")
    line = f"Archive DOI: https://doi.org/{doi}"
    section = f"### Archive DOI\n\n{line}"
    if "### Archive DOI" in body:
        new_body = re.sub(
            r"### Archive DOI\n\n.*?(?=\n### |\Z)",
            section,
            body,
            flags=re.DOTALL,
        )
    elif "Archive DOI:" not in body:
        new_body = body.rstrip() + "\n\n" + section + "\n"
    elif line in body:
        new_body = body
    else:
        new_body = re.sub(r"Archive DOI:.*", line, body)
    changed = new_body != body
    if changed and write:
        subprocess.run(
            ["gh", "release", "edit", tag, "--repo", repo, "--notes", new_body],
            check=True,
        )
    return changed


def main() -> int:
    args = parse_args()
    try:
        doi = normalize_doi(args.doi)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    write = not args.check
    changes = {
        "citation": update_citation(ROOT / "CITATION.cff", doi, write=write),
        "zenodo": update_zenodo(ROOT / ".zenodo.json", doi, write=write),
    }
    if args.update_github_release:
        changes["github_release"] = update_github_release(args.repo, args.tag, doi, write=write)

    print(
        json.dumps(
            {
                "ok": True,
                "doi": doi,
                "wrote_files": write,
                "changes": changes,
                "next_command": "uv run python scripts/check_release_metadata.py",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
