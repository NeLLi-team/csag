#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from csag.cli import build_parser


ROOT = Path(__file__).resolve().parents[1]
DOC_PATHS = [
    ROOT / "README.md",
    ROOT / "docs/release-process.md",
    ROOT / "docs/developer-guide.md",
    ROOT / "docs/benchmark-support.md",
    ROOT / "docs/interoperability.md",
    ROOT / "docs/profiles.md",
    ROOT / "docs/handoff-envelope.md",
    ROOT / "examples/README.md",
    ROOT / "examples/toy/README.md",
]
REQUIRED_DOC_SNIPPETS = [
    "--profile paper_local",
    "--profile promoted_claim",
    "--profile benchmark_key",
    "--profile handoff",
    "--format jsonld",
    "--format graphml",
    "--format rdf",
    "--format table",
    "--format ro-crate",
    "--answer-key",
    "--participant",
    "--scoring-schema",
    "csag doctor",
    "csag quickstart",
    "csag check-examples",
    "--api-key",
    "--pdf-mode auto",
]

REQUIRED_COMMAND_OPTIONS = {
    "ingest": ["--api-key", "--base-url", "--output-dir", "--pdf-mode"],
    "doctor": ["--api-key", "--base-url", "--report-out", "--strict"],
    "report": ["--article-json", "--report-out", "--source-markdown", "--strict"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check public CLI commands are documented.")
    parser.add_argument("--report-out", type=Path)
    return parser.parse_args()


def public_commands() -> list[str]:
    parser = build_parser()
    subparser_actions = [
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    ]
    if not subparser_actions:
        return []
    return sorted(subparser_actions[0].choices)


def public_command_options() -> dict[str, list[str]]:
    parser = build_parser()
    subparser_actions = [
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    ]
    if not subparser_actions:
        return {}
    options: dict[str, list[str]] = {}
    for name, command_parser in subparser_actions[0].choices.items():
        command_options = sorted(
            option
            for action in command_parser._actions
            for option in action.option_strings
            if option.startswith("--")
        )
        options[name] = command_options
    return options


def main() -> int:
    args = parse_args()
    docs = "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS if path.exists())
    commands = public_commands()
    command_options = public_command_options()
    missing = [command for command in commands if f"csag {command}" not in docs]
    missing_snippets = [snippet for snippet in REQUIRED_DOC_SNIPPETS if snippet not in docs]
    missing_options = {
        command: [option for option in required if option not in command_options.get(command, [])]
        for command, required in REQUIRED_COMMAND_OPTIONS.items()
    }
    missing_options = {command: options for command, options in missing_options.items() if options}
    report = {
        "ok": not missing and not missing_snippets and not missing_options,
        "commands": commands,
        "command_options": command_options,
        "required_command_options": REQUIRED_COMMAND_OPTIONS,
        "required_snippets": REQUIRED_DOC_SNIPPETS,
        "doc_paths": [str(path.relative_to(ROOT)) for path in DOC_PATHS if path.exists()],
        "missing": missing,
        "missing_snippets": missing_snippets,
        "missing_options": missing_options,
    }
    if args.report_out:
        args.report_out.expanduser().resolve().write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if missing or missing_snippets or missing_options else 0


if __name__ == "__main__":
    raise SystemExit(main())
