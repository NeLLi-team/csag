from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .paths import CommandResult, ROOT, run_python_capture


def build_quality_report(
    extraction_json: Path,
    *,
    source_markdown: Path | None = None,
    article_json: Path | None = None,
    openalex_json: Path | None = None,
    report_out: Path | None = None,
    strict: bool = False,
    document_scope: str = "auto",
    analysis_year: int | None = None,
) -> CommandResult:
    with tempfile.TemporaryDirectory(prefix="csag-report-api-") as temp_name:
        extraction_json = extraction_json.expanduser().resolve()
        source_markdown = source_markdown.expanduser().resolve() if source_markdown else None
        article_json = article_json.expanduser().resolve() if article_json else None
        openalex_json = openalex_json.expanduser().resolve() if openalex_json else None
        out = report_out.expanduser().resolve() if report_out else Path(temp_name) / "quality.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        args = [str(extraction_json), "--document-scope", document_scope, "--report-out", str(out)]
        if source_markdown:
            args.extend(["--source-markdown", str(source_markdown)])
        if article_json:
            args.extend(["--article-json", str(article_json)])
        if openalex_json:
            args.extend(["--openalex-json", str(openalex_json)])
        if analysis_year is not None:
            args.extend(["--analysis-year", str(analysis_year)])
        if strict:
            args.append("--strict")
        result = run_python_capture(ROOT / "skills/csag-extraction/scripts/csag_quality_report.py", args)
        data = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
        return CommandResult(result.ok, result.exit_code, out if report_out and out.exists() else None, data, result.stdout, result.stderr)
