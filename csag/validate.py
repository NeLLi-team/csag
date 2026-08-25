from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .paths import CommandResult, ROOT, run_python_capture


def validate_extraction(extraction_json: Path, *, source_markdown: Path | None = None, article_json: Path | None = None, profile: str = "paper_local", report_out: Path | None = None) -> CommandResult:
    with tempfile.TemporaryDirectory(prefix="csag-validate-api-") as temp_name:
        if profile == "handoff" and (source_markdown or article_json):
            return CommandResult(
                False,
                2,
                stderr="source_markdown and article_json apply only to PaperExtraction validation\n",
            )
        extraction_json = extraction_json.expanduser().resolve()
        source_markdown = source_markdown.expanduser().resolve() if source_markdown else None
        article_json = article_json.expanduser().resolve() if article_json else None
        out = report_out.expanduser().resolve() if report_out else Path(temp_name) / "validation.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        args = [str(extraction_json), "--profile", profile, "--report-out", str(out)]
        if source_markdown:
            args.extend(["--source-markdown", str(source_markdown)])
        if article_json:
            args.extend(["--article-json", str(article_json)])
        validator_script = (
            ROOT / "skills/csag-extraction/scripts/validate_handoff_envelope.py"
            if profile == "handoff"
            else ROOT / "skills/csag-extraction/scripts/validate_paper_extraction.py"
        )
        result = run_python_capture(validator_script, args)
        data = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
        if report_out is None and data is not None:
            return CommandResult(result.ok, result.exit_code, None, data, result.stdout, result.stderr)
        return CommandResult(result.ok, result.exit_code, out if out.exists() else None, data, result.stdout, result.stderr)
