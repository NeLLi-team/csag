from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .export import export_extraction
from .ingest import check_http, ingest_manuscript, ocr_base_url
from .inspect import inspect_workdir
from .lint import lint_extraction
from .paths import ROOT, run_python
from .scaffold import scaffold_extraction
from .score import score_extraction


def cmd_ingest(args: argparse.Namespace) -> int:
    result = ingest_manuscript(
        args.input,
        output_dir=args.output_dir,
        pdf_mode=args.pdf_mode,
        base_url=args.base_url,
        api_key=args.api_key,
    )
    return result.exit_code


def cmd_validate(args: argparse.Namespace) -> int:
    extraction_json = args.extraction_json.expanduser().resolve()
    report_out = args.report_out.expanduser().resolve()
    report_out.parent.mkdir(parents=True, exist_ok=True)
    call_args = [
        str(extraction_json),
        "--profile",
        args.profile,
        "--report-out",
        str(report_out),
    ]
    if args.profile == "handoff":
        if args.source_markdown or args.article_json:
            print(
                "--source-markdown and --article-json apply only to PaperExtraction validation.",
                file=sys.stderr,
            )
            return 2
        return run_python(
            ROOT / "skills/csag-extraction/scripts/validate_handoff_envelope.py",
            call_args,
        )
    if args.source_markdown:
        call_args.extend(["--source-markdown", str(args.source_markdown.expanduser().resolve())])
    if args.article_json:
        call_args.extend(["--article-json", str(args.article_json.expanduser().resolve())])
    return run_python(ROOT / "skills/csag-extraction/scripts/validate_paper_extraction.py", call_args)


def cmd_report(args: argparse.Namespace) -> int:
    extraction_json = args.extraction_json.expanduser().resolve()
    call_args = [str(extraction_json)]
    if args.source_markdown:
        call_args.extend(["--source-markdown", str(args.source_markdown.expanduser().resolve())])
    if getattr(args, "article_json", None):
        call_args.extend(["--article-json", str(args.article_json.expanduser().resolve())])
    if getattr(args, "openalex_json", None):
        call_args.extend(["--openalex-json", str(args.openalex_json.expanduser().resolve())])
    if args.report_out:
        report_out = args.report_out.expanduser().resolve()
        report_out.parent.mkdir(parents=True, exist_ok=True)
        call_args.extend(["--report-out", str(report_out)])
    if getattr(args, "document_scope", None):
        call_args.extend(["--document-scope", args.document_scope])
    if getattr(args, "analysis_year", None):
        call_args.extend(["--analysis-year", str(args.analysis_year)])
    if args.strict:
        call_args.append("--strict")
    return run_python(ROOT / "skills/csag-extraction/scripts/csag_quality_report.py", call_args)


def cmd_export(args: argparse.Namespace) -> int:
    result = export_extraction(args.extraction_json, format=args.format, output=args.output)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.exit_code


def cmd_scaffold(args: argparse.Namespace) -> int:
    result = scaffold_extraction(args.markdown, article_json=args.article_json, output=args.output, profile=args.profile)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.exit_code


def cmd_inspect(args: argparse.Namespace) -> int:
    report = inspect_workdir(args.workdir)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"workdir: {report['workdir']}")
        print(f"state: {report['state']}")
        for name, info in report["files"].items():
            status = "present" if info.get("present") else "missing"
            extra = ""
            if info.get("present") and "ok" in info:
                extra = f" ok={info['ok']}"
            print(f"  {name}: {status}{extra}")
        print(f"next: {report['suggested_next_command']}")
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    return lint_extraction(args.extraction_json, report_out=args.report_out, strict=args.strict).exit_code


def cmd_score(args: argparse.Namespace) -> int:
    result = score_extraction(
        answer_key=args.answer_key,
        participant=args.participant,
        scoring_schema=args.scoring_schema,
        report_out=args.report_out,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.exit_code


def cmd_doctor(args: argparse.Namespace) -> int:
    pdf_path = args.pdf.expanduser().resolve() if args.pdf else None
    env_key_name = "OCR_API_KEY" if os.getenv("OCR_API_KEY") else "NELLI_API_KEY" if os.getenv("NELLI_API_KEY") else ""
    env_key_value = os.getenv(env_key_name, "") if env_key_name else ""
    explicit_key_value = getattr(args, "api_key", None) or ""
    api_key_value = explicit_key_value or env_key_value
    explicit_key = bool(explicit_key_value)
    key_source = "argument" if explicit_key else env_key_name
    base_url = ocr_base_url(args.base_url)
    selected_ok, selected_detail = check_http(f"{base_url}/health", api_key=api_key_value or None)
    base_url_pinned = bool(args.base_url or os.getenv("OCR_BASE_URL"))
    checks = {
        "pdf_readable": (pdf_path.exists() and pdf_path.is_file()) if pdf_path else None,
        "ocr_api_key_available": bool(api_key_value),
        "ocr_api_key_source": key_source,
        "selected_ocr_base_url": base_url,
        "selected_ocr_health": {"ok": selected_ok, "detail": selected_detail},
        "selected_ocr_base_url_pinned": base_url_pinned,
    }
    checks["ready_for_ocr_extract"] = (
        checks["pdf_readable"] is not False
        and checks["ocr_api_key_available"]
        and selected_ok
    )
    if args.report_out:
        args.report_out.expanduser().resolve().write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(checks, indent=2))
    return 1 if args.strict and not checks["ready_for_ocr_extract"] else 0


def cmd_check_examples(args: argparse.Namespace) -> int:
    examples_dir = args.examples_dir.expanduser().resolve()
    if args.report_dir:
        args.report_dir.expanduser().resolve().mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    failures = 0

    example_dirs = {
        path.parent
        for pattern in ("example_manifest.json", "paper_extraction.json")
        for path in examples_dir.rglob(pattern)
    }
    for example_dir in sorted(example_dirs):
        entry: dict = {"example": str(example_dir), "checks": []}
        manifest = example_dir / "example_manifest.json"
        manifest_payload = {}
        if manifest.exists():
            try:
                manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                manifest_payload = {}
            code = run_python(ROOT / "scripts/verify_example_manifest.py", [str(manifest)])
            entry["checks"].append({"name": "manifest", "ok": code == 0})
            failures += int(code != 0)

        extraction = example_dir / "paper_extraction.json"
        if extraction.exists():
            markdowns = sorted(path for path in example_dir.glob("*.md") if path.name.lower() != "readme.md")
            article_jsons = sorted(example_dir.glob("*.article.json"))
            source_markdown = markdowns[0] if markdowns else None
            article_json = article_jsons[0] if article_jsons else None

            validation_report = example_dir / "paper_extraction.validation.json"
            validate_args = argparse.Namespace(
                extraction_json=extraction,
                source_markdown=source_markdown,
                article_json=article_json,
                profile=manifest_payload.get("validation_profile", "paper_local"),
                report_out=validation_report,
            )
            code = cmd_validate(validate_args)
            entry["checks"].append({"name": "validate", "ok": code == 0})
            failures += int(code != 0)

            quality_report = example_dir / "paper_extraction.quality.json"
            report_args = argparse.Namespace(
                extraction_json=extraction,
                source_markdown=source_markdown,
                article_json=article_json,
                openalex_json=None,
                analysis_year=None,
                report_out=quality_report,
                strict=True,
                document_scope=manifest_payload.get("document_scope", "auto"),
            )
            code = cmd_report(report_args)
            entry["checks"].append({"name": "report", "ok": code == 0})
            failures += int(code != 0)

            lint_report = args.report_dir / f"{example_dir.name}.lint.json" if args.report_dir else None
            lint_args = argparse.Namespace(extraction_json=extraction, report_out=lint_report, strict=True)
            code = cmd_lint(lint_args)
            entry["checks"].append({"name": "lint", "ok": code == 0})
            failures += int(code != 0)

        if entry["checks"]:
            results.append(entry)

    if args.coverage_out:
        run_python(
            ROOT / "scripts/collect_example_metrics.py",
            ["--examples-dir", str(examples_dir), "--report-out", str(args.coverage_out)],
        )

    summary = {"ok": failures == 0, "examples_checked": len(results), "results": results}
    if args.report_out:
        args.report_out.expanduser().resolve().write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(summary, indent=2))
    return 1 if failures else 0


def cmd_quickstart(args: argparse.Namespace) -> int:
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    example_dir = ROOT / "examples/toy"
    extraction = example_dir / "paper_extraction.json"
    source_markdown = example_dir / "toy.md"
    article_json = example_dir / "toy.article.json"

    checks: list[dict] = []
    failures = 0

    validate_args = argparse.Namespace(
        extraction_json=extraction,
        source_markdown=source_markdown,
        article_json=article_json,
        profile="paper_local",
        report_out=output_dir / "toy.validation.json",
    )
    code = cmd_validate(validate_args)
    checks.append({"name": "validate", "ok": code == 0, "report": str(validate_args.report_out)})
    failures += int(code != 0)

    report_args = argparse.Namespace(
        extraction_json=extraction,
        source_markdown=source_markdown,
        article_json=article_json,
        report_out=output_dir / "toy.quality.json",
        strict=True,
    )
    code = cmd_report(report_args)
    checks.append({"name": "report", "ok": code == 0, "report": str(report_args.report_out)})
    failures += int(code != 0)

    lint_args = argparse.Namespace(
        extraction_json=extraction,
        report_out=output_dir / "toy.lint.json",
        strict=True,
    )
    code = cmd_lint(lint_args)
    checks.append({"name": "lint", "ok": code == 0, "report": str(lint_args.report_out)})
    failures += int(code != 0)

    summary = {"ok": failures == 0, "example": str(example_dir), "output_dir": str(output_dir), "checks": checks}
    print(json.dumps(summary, indent=2))
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="csag", description="CSAG extraction, validation, reporting, and export tools.")
    parser.add_argument("--version", action="version", version=f"csag {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_ingest_args(command: argparse.ArgumentParser) -> None:
        command.add_argument("input", type=Path)
        command.add_argument("--output-dir", type=Path)
        command.add_argument(
            "--pdf-mode",
            choices=("ocr", "local", "auto"),
            default="ocr",
            help="PDF conversion mode: OCR API, local LiteParse, or OCR with local fallback.",
        )
        command.add_argument("--base-url")
        command.add_argument("--api-key")

    ingest = subparsers.add_parser("ingest", help="Convert a PDF or Markdown manuscript into Markdown/article sidecars.")
    add_ingest_args(ingest)
    ingest.set_defaults(func=cmd_ingest)

    validate = subparsers.add_parser("validate", help="Validate a PaperExtraction or HandoffEnvelope JSON file.")
    validate.add_argument("extraction_json", type=Path)
    validate.add_argument("--source-markdown", type=Path)
    validate.add_argument("--article-json", type=Path)
    validate.add_argument(
        "--profile",
        default="paper_local",
        help=(
            "Validation profile. Existing strictness profiles: lite, paper_local, "
            "promoted_claim, benchmark_key. Module profiles may be used alone or "
            "comma-combined: core, bio, reasoning, research_state, benchmark. Use "
            "handoff for a HandoffEnvelope."
        ),
    )
    validate.add_argument("--report-out", type=Path, required=True)
    validate.set_defaults(func=cmd_validate)

    report = subparsers.add_parser("report", help="Build a quality report for a paper_extraction.json file.")
    report.add_argument("extraction_json", type=Path)
    report.add_argument("--source-markdown", type=Path)
    report.add_argument("--article-json", type=Path)
    report.add_argument("--openalex-json", type=Path)
    report.add_argument("--report-out", type=Path)
    report.add_argument("--document-scope", choices=("lite", "short_note", "full_article", "benchmark_key", "auto"), default="auto")
    report.add_argument("--analysis-year", type=int)
    report.add_argument("--strict", action="store_true")
    report.set_defaults(func=cmd_report)

    scaffold = subparsers.add_parser("scaffold", help="Create a draft Lite paper_extraction.json from Markdown and article sidecar.")
    scaffold.add_argument("markdown", type=Path)
    scaffold.add_argument("--article-json", type=Path, required=True)
    scaffold.add_argument("--output", type=Path, required=True)
    scaffold.add_argument("--profile", choices=("lite", "paper_local"), default="lite")
    scaffold.set_defaults(func=cmd_scaffold)

    inspect = subparsers.add_parser("inspect", help="Inspect a CSAG work directory and suggest the next command.")
    inspect.add_argument("workdir", type=Path)
    inspect.add_argument("--json", action="store_true")
    inspect.set_defaults(func=cmd_inspect)

    export = subparsers.add_parser("export", help="Export CSAG JSON into exchange formats.")
    export.add_argument("extraction_json", type=Path)
    export.add_argument("--format", choices=("json", "jsonld", "graphml", "rdf", "table", "ro-crate"), required=True)
    export.add_argument("--output", type=Path, required=True)
    export.set_defaults(func=cmd_export)

    lint = subparsers.add_parser("lint", help="Check stable IDs, grounding, and source document consistency.")
    lint.add_argument("extraction_json", type=Path)
    lint.add_argument("--report-out", type=Path)
    lint.add_argument("--strict", action="store_true")
    lint.set_defaults(func=cmd_lint)

    score = subparsers.add_parser("score", help="Score a participant CSAG against a benchmark answer key.")
    score.add_argument("--answer-key", type=Path, required=True)
    score.add_argument("--participant", type=Path, required=True)
    score.add_argument("--scoring-schema", type=Path, required=True)
    score.add_argument("--report-out", type=Path, required=True)
    score.set_defaults(func=cmd_score)

    doctor = subparsers.add_parser("doctor", help="Check local prerequisites for OCR-based PDF extraction.")
    doctor.add_argument("--pdf", type=Path)
    doctor.add_argument("--base-url")
    doctor.add_argument("--api-key")
    doctor.add_argument("--report-out", type=Path)
    doctor.add_argument("--strict", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    check_examples = subparsers.add_parser("check-examples", help="Validate, report, lint, and verify example manifests.")
    check_examples.add_argument("--examples-dir", type=Path, default=ROOT / "examples")
    check_examples.add_argument("--report-out", type=Path)
    check_examples.add_argument("--report-dir", type=Path)
    check_examples.add_argument("--coverage-out", type=Path)
    check_examples.set_defaults(func=cmd_check_examples)

    quickstart = subparsers.add_parser("quickstart", help="Run the toy example validation, report, and lint workflow.")
    quickstart.add_argument("--output-dir", type=Path, default=Path("/tmp/csag-quickstart"))
    quickstart.set_defaults(func=cmd_quickstart)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
