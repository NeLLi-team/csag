# Developer guide

## Schema source and repository root

The authoritative schema is the LinkML (Linked Data Modeling Language) source
`skills/csag-extraction/assets/csag.yaml`. Two kinds of artifacts are
generated from it: the JSON Schema files `csag.schema.json` and
`csag.handoff.schema.json` in the same `skills/csag-extraction/assets/`
directory, and the Markdown reference `schema/csag.md`. Regenerate them after
every schema edit:

```bash
uv run python scripts/generate_schema_artifacts.py
```

Check that the committed artifacts match the schema without rewriting them:

```bash
uv run python scripts/check_schema_artifacts.py
```

The `csag` command runs the workflow scripts under `skills/` and `scripts/`,
so it needs a repository checkout. To run it from another working directory,
point it at the checkout:

```bash
export CSAG_REPO_ROOT=/path/to/CSAG
```

## Staged workflow commands

[CSAG Lite](csag-lite.md) lists the seven stages with complete commands. Each
stage is one subcommand.

| Command | What it does |
|---------|--------------|
| `csag ingest` | Converts a PDF or Markdown manuscript into canonical Markdown plus the `article.json` and `section_audit.json` sidecars in a work directory. |
| `csag scaffold` | Writes a draft Lite `paper_extraction.json` from the Markdown and the article sidecar. |
| `csag inspect` | Reads a work directory, reports which files are present and fresh, and prints the next command. |
| `csag validate` | Validates a `PaperExtraction` or `HandoffEnvelope` file against a profile and writes a validation report. |
| `csag report` | Builds the quality report: coverage, completeness, grounding, field-level information quality, per-claim readouts, and conversion-quality scores. With `--openalex-json` (a saved OpenAlex Work response) and `--analysis-year`, it adds age-normalized citation context. |
| `csag lint` | Checks stable IDs, grounding, and source document consistency and writes a lint report. |
| `csag export` | Writes the extraction as JSON, JSON-LD (JSON for Linking Data), RDF (Resource Description Framework), GraphML, a TSV table, or an RO-Crate (Research Object Crate). |

The same operations are available as a Python API:

```python
from csag import (
    CommandResult,
    ingest_manuscript,
    scaffold_extraction,
    inspect_workdir,
    validate_extraction,
    build_quality_report,
    lint_extraction,
    export_extraction,
    score_extraction,
)
```

## Validators

Validator logic lives in
`skills/csag-extraction/scripts/validate_paper_extraction.py` for
`PaperExtraction` files and in
`skills/csag-extraction/scripts/validate_handoff_envelope.py` for
`HandoffEnvelope` files; `csag validate` calls the right one. Give every check
an object ID, a field path, a reason, and a suggested fix so that reports stay
actionable.

Use `--profile core,research_state` to validate the optional current-read,
next-action, and execution objects. Neither the `lite` nor the `paper_local`
profile requires them.

## Exporters

Export implementations live in `csag/export.py`; `csag/cli.py` only
dispatches the command. Keep every format deterministic.
[Interoperability](interoperability.md) lists the fidelity of each format.

## Add vocabulary terms

Add a controlled vocabulary term to the LinkML enum first, regenerate the
schema artifacts, and add a validation fixture if the term changes validator
behavior.
