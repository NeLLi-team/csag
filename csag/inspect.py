from __future__ import annotations

import json
from pathlib import Path
import shlex

from .provenance import check_report_inputs


def _json_status(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"valid_json": False, "error": str(exc)}
    status = {"valid_json": True}
    if isinstance(data, dict):
        if "ok" in data:
            status["ok"] = bool(data.get("ok"))
        if "issues" in data and isinstance(data.get("issues"), list):
            status["issue_count"] = len(data["issues"])
    return status


def _file_info(path: Path) -> dict:
    if not path.exists():
        return {"present": False}
    stat = path.stat()
    info = {"present": True, "size_bytes": stat.st_size, "modified_unix": int(stat.st_mtime)}
    if path.suffix == ".json":
        info.update(_json_status(path))
    return info


def _report_freshness(path: Path) -> dict:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"fresh": False, "stale_inputs": [{"input": "(report)", "reason": "invalid JSON"}]}
    fresh, stale = check_report_inputs(path, report)
    return {"fresh": fresh, "stale_inputs": stale}


def _validate_command(expected: dict, files: dict) -> str:
    parts = ["csag", "validate", str(expected["extraction"])]
    if files["markdown"]["present"]:
        parts.extend(["--source-markdown", str(expected["markdown"])])
    if files["article_json"]["present"]:
        parts.extend(["--article-json", str(expected["article_json"])])
    parts.extend(["--profile", "lite", "--report-out", str(expected["validation"])])
    return shlex.join(parts)


def _report_command(expected: dict, files: dict) -> str:
    parts = ["csag", "report", str(expected["extraction"])]
    if files["markdown"]["present"]:
        parts.extend(["--source-markdown", str(expected["markdown"])])
    if files["article_json"]["present"]:
        parts.extend(["--article-json", str(expected["article_json"])])
    parts.extend(["--report-out", str(expected["quality"])])
    return shlex.join(parts)


def inspect_workdir(workdir: Path) -> dict:
    workdir = workdir.expanduser().resolve()
    markdowns = sorted(path for path in workdir.glob("*.md") if path.name.lower() != "readme.md") if workdir.exists() else []
    stem = markdowns[0].stem if markdowns else workdir.name
    expected = {
        "markdown": workdir / f"{stem}.md",
        "section_audit": workdir / f"{stem}.section_audit.json",
        "article_json": workdir / f"{stem}.article.json",
        "extraction": workdir / "paper_extraction.json",
        "validation": workdir / "paper_extraction.validation.json",
        "quality": workdir / "paper_extraction.quality.json",
        "lint": workdir / "paper_extraction.lint.json",
    }
    files = {name: _file_info(path) for name, path in expected.items()}
    for name in ("validation", "quality", "lint"):
        if files[name]["present"]:
            files[name].update(_report_freshness(expected[name]))
    extraction_present = files["extraction"]["present"]
    if not workdir.exists() or not any(workdir.iterdir()):
        state = "empty_or_missing"
        next_command = shlex.join(["csag", "ingest", "<input>", "--output-dir", str(workdir)])
    elif not extraction_present and not files["markdown"]["present"]:
        state = "missing_markdown"
        next_command = shlex.join(["csag", "ingest", "<input>", "--output-dir", str(workdir)])
    elif not extraction_present and not files["article_json"]["present"]:
        state = "markdown_only"
        next_command = shlex.join(["csag", "ingest", str(expected["markdown"]), "--output-dir", str(workdir)])
    elif not extraction_present:
        state = "ingested"
        next_command = shlex.join(
            [
                "csag",
                "scaffold",
                str(expected["markdown"]),
                "--article-json",
                str(expected["article_json"]),
                "--output",
                str(expected["extraction"]),
                "--profile",
                "lite",
            ]
        )
    elif not files["validation"]["present"]:
        state = "scaffolded_or_curated"
        next_command = _validate_command(expected, files)
    elif not files["validation"].get("valid_json", False):
        state = "validation_failed"
        next_command = "fix paper_extraction.json, rerun csag validate"
    elif not files["validation"].get("fresh", False):
        state = "validation_stale"
        next_command = _validate_command(expected, files)
    elif files["validation"].get("ok") is False:
        state = "validation_failed"
        next_command = "fix paper_extraction.json, rerun csag validate"
    elif not files["quality"]["present"]:
        state = "validated"
        next_command = _report_command(expected, files)
    elif not files["quality"].get("valid_json", False):
        state = "quality_failed"
        next_command = "fix paper_extraction.json, rerun csag report"
    elif not files["quality"].get("fresh", False):
        state = "quality_stale"
        next_command = _report_command(expected, files)
    elif files["quality"].get("ok") is False or files["quality"].get("issue_count", 0) > 0:
        state = "quality_failed"
        next_command = "fix paper_extraction.json, rerun csag report"
    elif not files["lint"]["present"]:
        state = "quality_reported"
        next_command = shlex.join(["csag", "lint", str(expected["extraction"]), "--report-out", str(expected["lint"]), "--strict"])
    elif not files["lint"].get("valid_json", False):
        state = "lint_failed"
        next_command = "fix paper_extraction.json, rerun csag lint"
    elif not files["lint"].get("fresh", False):
        state = "lint_stale"
        next_command = shlex.join(["csag", "lint", str(expected["extraction"]), "--report-out", str(expected["lint"]), "--strict"])
    elif files["lint"].get("ok") is False:
        state = "lint_failed"
        next_command = "fix paper_extraction.json, rerun csag lint"
    else:
        state = "complete"
        next_command = "ready to export"
    ready = state == "complete"
    return {
        "workdir": str(workdir),
        "stem": stem,
        "state": state,
        "files": {name: {"path": str(expected[name]), **info} for name, info in files.items()},
        "suggested_next_command": next_command,
        "ready_to_export": ready,
    }
