# CSAG

A Conditional Scientific Argumentation Graph (CSAG) is a machine-readable
representation of the argumentation structure of a scientific manuscript. It
records the manuscript's claims as assertions, each scoped by at least one
context, and the manuscript's results as evidence items. Evidence links connect
evidence items to assertions with a support or refute polarity. Study
critiques, knowledge gaps, artifacts, datasets, and provenance records complete
the core, and text spans ground each object in the source text. Optional
modules add biological entity normalization, explicit reasoning chains,
research-state records, and benchmark answer keys.

This repository provides the schema, the validator, the `csag` command-line
tools and Python API, and worked examples for creating and inspecting CSAG
artifacts. A separate manuscript, in preparation, describes the
concept and its motivation.

## Installation

```bash
uv sync                          # core dependencies
uv sync --extra local-pdf        # adds LiteParse for local PDF conversion
```

`csag` runs the scripts under `skills/` and `scripts/` from the repository
checkout. If it reports a missing repository resource, set `CSAG_REPO_ROOT` to
the checkout path.

## Workflow

The workflow converts one manuscript into a work directory, drafts a
CSAG Lite extraction, and checks it. CSAG Lite is the six-object subset of the
schema that [docs/csag-lite.md](docs/csag-lite.md) describes, and
[docs/extraction-density-targets.md](docs/extraction-density-targets.md)
describes how much a well-covered extraction contains. The work directory is
your choice; the commands use `work/paper/`, which git ignores.

```bash
# 1. Ingest a PDF or Markdown manuscript into Markdown and article sidecars
uv run csag ingest manuscript.md --output-dir work/paper/

# 2. Scaffold a draft Lite paper_extraction.json
uv run csag scaffold work/paper/manuscript.md \
  --article-json work/paper/manuscript.article.json \
  --output work/paper/paper_extraction.json \
  --profile lite

# 3. Inspect the work directory and print the suggested next command
uv run csag inspect work/paper/

# 4. Validate against the lite profile
uv run csag validate work/paper/paper_extraction.json \
  --source-markdown work/paper/manuscript.md \
  --article-json work/paper/manuscript.article.json \
  --profile lite \
  --report-out work/paper/paper_extraction.validation.json

# 5. Build the quality report with the lite document scope
uv run csag report work/paper/paper_extraction.json \
  --source-markdown work/paper/manuscript.md \
  --article-json work/paper/manuscript.article.json \
  --document-scope lite \
  --report-out work/paper/paper_extraction.quality.json

# 6. Lint stable IDs and grounding
uv run csag lint work/paper/paper_extraction.json \
  --report-out work/paper/paper_extraction.lint.json

# 7. Export the extraction, source files, and reports as an RO-Crate bundle
uv run csag export work/paper/paper_extraction.json \
  --format ro-crate --output work/paper/ro-crate
```

Curate `paper_extraction.json` between steps 2 and 4: the scaffold is a draft,
and `skills/csag-extraction/SKILL.md` holds the extraction rules. The
validation, quality, and lint reports record SHA-256 hashes of their inputs,
and `csag inspect` marks a report as stale when an input changed after the
report was written.

The quality report summarizes coverage, completeness, grounding, field
quality, per-claim readouts, and conversion quality. With a saved OpenAlex Work
record (`--openalex-json` and `--analysis-year`) it adds literature-quality
context; citation metrics describe literature reach and do not verify claims.

## Conversion modes

`csag ingest` accepts a PDF or a Markdown file. For a PDF, `--pdf-mode` selects
the conversion engine: the OCR (optical character recognition) API or
LiteParse.

| Mode | Engine | Needs |
|------|--------|-------|
| `ocr` (default) | OCR API | `OCR_API_KEY` or `NELLI_API_KEY`, or `--api-key` |
| `local` | LiteParse | the `local-pdf` extra |
| `auto` | OCR API, then LiteParse if the OCR API fails; LiteParse alone when no key is set | as for the engine used |

```bash
uv run csag ingest paper.pdf --output-dir work/paper/ --pdf-mode ocr
uv run csag ingest paper.pdf --output-dir work/paper/ --pdf-mode local
uv run csag ingest paper.pdf --output-dir work/paper/ --pdf-mode auto
```

Both engines write `<stem>.md`. `csag ingest` then writes `<stem>.article.json`
and `<stem>.section_audit.json` next to it and validates the article sidecar.
`skills/pdf-to-md/SKILL.md` describes both engines and how to shape LiteParse
output.

## OCR service

The `csag` client reads the OCR API key from `OCR_API_KEY` or
`NELLI_API_KEY`, or from `--api-key`. The client uses
`https://api.newlineages.com/ocr` unless `OCR_BASE_URL` or `--base-url` names
another service; to use a local service, set
`OCR_BASE_URL=http://127.0.0.1:8002/ocr`. The base URL must use HTTPS, or HTTP
on localhost; a base URL never replaces the key.
`csag doctor` reports whether the PDF is readable, whether a key is available,
and whether the selected service responds:

```bash
uv run csag doctor --pdf paper.pdf \
  --api-key <key> \
  --base-url http://127.0.0.1:8002/ocr \
  --report-out /tmp/csag-doctor.json

uv run csag ingest paper.pdf \
  --output-dir work/paper/ \
  --api-key <key> \
  --base-url http://127.0.0.1:8002/ocr
```

`scripts/local_tesseract_ocr_api.py` serves the same OCR API contract on the
local endpoint with `pdftoppm` and `tesseract`, for development without the
remote service:

```bash
TESSDATA_PREFIX=/path/to/tessdata \
  uv run python scripts/local_tesseract_ocr_api.py --api-key local-ocr-key
```

## Schema

The authoritative schema is the LinkML (Linked Data Modeling Language) source
`skills/csag-extraction/assets/csag.yaml`. The generated JSON Schema files
`csag.schema.json` and `csag.handoff.schema.json` sit next to it, and the
generated Markdown reference is `schema/csag.md`. The schema has one mandatory
core module and four optional modules:

| Module | Classes | Purpose |
|--------|---------|---------|
| `core` | `PaperExtraction`, `TextSpan`, `Assertion`, `Context`, `EvidenceItem`, `EvidenceLink`, `StudyCritique`, `KnowledgeGap`, `Artifact`, `Dataset` | The paper-local claim and evidence ledger. |
| `bio` | `Entity`, `EntityMention`, `OntologyAnnotation`, `Condition`, `Qualifier`, `Study`, `Experiment`, `Variable` | Biological normalization and study enrichment. |
| `reasoning` | `InferenceStep`, `AssertionRelation` | Derived reasoning chains and claim-to-claim relations. |
| `research_state` | `ResearchStateRecord`, `NextAction`, `Execution` | Paper-local research-state records, next actions, and runs. |
| `benchmark` | `QAItem`, `Answer` | Answer keys and scoring surfaces. |

The validator enforces six structural rules:

1. Every assertion has at least one context.
2. Support and refute polarity appears only in evidence links.
3. Contradiction, qualification, and replication appear only in assertion
   relations.
4. Reasoning chains appear only in inference steps.
5. Core and major objects are grounded with text spans.
6. Every assertion carries a normalization status.

Two `Assertion` slots serve evaluation: `criticality` (`core`, `major`,
`supporting`, or `background`) and `falsification_criteria` (the observation
that would weaken or refute the claim).
[docs/entity-normalization.md](docs/entity-normalization.md) describes entity
normalization, with a worked supplement under
`supplementary/entity-normalization/`.

## Validation profiles

| Profile | Use |
|---------|-----|
| `lite` | Starting point for an extraction; checks the six Lite object types. |
| `core` / `paper_local` | Full profile for one manuscript extraction. |
| `core,bio` | Core plus biological normalization warnings. |
| `core,reasoning` | Core plus inference and relation warnings. |
| `core,research_state` | Core plus research-state warnings. |
| `promoted_claim` | Curated claims ready for reuse. |
| `core,benchmark` / `benchmark_key` | Answer-key artifacts for scoring. |
| `handoff` | `HandoffEnvelope` exchange records. |

```bash
uv run csag validate examples/toy/paper_extraction.json \
  --source-markdown examples/toy/toy.md \
  --article-json examples/toy/toy.article.json \
  --profile paper_local \
  --report-out /tmp/toy.validation.json

uv run csag validate tests/fixtures/validation_profiles/promoted_claim.valid.json \
  --profile promoted_claim \
  --report-out /tmp/promoted.validation.json

uv run csag validate tests/fixtures/validation_profiles/benchmark_key.valid.json \
  --profile benchmark_key \
  --report-out /tmp/benchmark.validation.json
```

[docs/profiles.md](docs/profiles.md) defines each profile and the failure
severities.

## Exports

`csag export` writes one `PaperExtraction` in six formats. Canonical JSON is
lossless. An RO-Crate (Research Object Crate) bundles the artifact with the
source Markdown, sidecars, and reports from the same directory and records a
SHA-256 hash for each included file. JSON-LD (JSON for Linking Data) and RDF
(Resource Description Framework, serialized as Turtle) are semantic
projections; GraphML and TSV (tab-separated values) are analysis views. These
four formats do not preserve the full artifact;
[docs/interoperability.md](docs/interoperability.md) lists the fidelity of
each format. The versioned [`HandoffEnvelope`](docs/handoff-envelope.md)
carries collaboration state between agents: revision heads, assessments,
owned actions, executions, and conflicts.

```bash
uv run csag export examples/toy/paper_extraction.json --format json --output /tmp/toy.json
uv run csag export examples/toy/paper_extraction.json --format jsonld --output /tmp/toy.jsonld
uv run csag export examples/toy/paper_extraction.json --format graphml --output /tmp/toy.graphml
uv run csag export examples/toy/paper_extraction.json --format rdf --output /tmp/toy.ttl
uv run csag export examples/toy/paper_extraction.json --format table --output /tmp/toy.tsv
uv run csag export examples/toy/paper_extraction.json --format ro-crate --output /tmp/toy-ro-crate
uv run csag validate tests/fixtures/handoff/two_agent_handoff.valid.json \
  --profile handoff --report-out /tmp/handoff.validation.json
```

## Benchmark scoring

`csag score` compares a participant extraction against a hidden answer key.
It matches assertions independently of local IDs and scores resolved context,
grounding, and evidence content:

```bash
uv run csag score \
  --answer-key tests/fixtures/benchmark/answer_key.hidden.json \
  --participant tests/fixtures/benchmark/participant_output.json \
  --scoring-schema tests/fixtures/benchmark/scoring_schema.json \
  --report-out /tmp/scored_report.json
```

## Examples

Three examples pair a redistributable source PDF with its Markdown, sidecars,
extraction, and reports. Each example manifest records the source license.

| Example | Source manuscript | License |
|---------|-------------------|---------|
| `examples/jamy2026/` | Jamy et al. 2026, Nature Communications, DOI 10.1038/s41467-025-67401-4 | CC BY 4.0 |
| `examples/prior-art/stocker2025_machine_readable/` | Stocker et al. 2025, Scientific Data, DOI 10.1038/s41597-025-04905-0 | CC BY 4.0 |
| `examples/prior-art/ciccarese2013_pav_ontology/` | Ciccarese et al. 2013, Journal of Biomedical Semantics, DOI 10.1186/2041-1480-4-37 | CC BY 2.0 |

`examples/toy/` and `examples/lite/` are synthetic manuscripts for
documentation and tests; `examples/pmid35150280/` ships an extraction and its
reports without source files; and
`examples/prior-art/soilandreyes2022_rocrate/` ships Markdown, sidecars,
extraction, and reports for a CC BY 4.0 manuscript without its PDF.
`examples/coverage_metrics.json` summarizes object coverage across the
examples.

Check the toy example (validate, report, and lint) or every example:

```bash
uv run csag quickstart --output-dir /tmp/csag-quickstart
uv run csag check-examples --examples-dir examples \
  --report-out /tmp/check-examples.json --coverage-out /tmp/coverage_metrics.json
```

## Evaluation

`csag score` compares extractions against answer keys (see Benchmark scoring);
[docs/evaluation-metrics.md](docs/evaluation-metrics.md) specifies the planned
metric families, and [docs/benchmark-support.md](docs/benchmark-support.md)
describes answer keys and the scorer. The repository publishes no benchmark
results.

## Repository layout

```text
csag/
├── README.md
├── AGENTS.md          # operating contract for extraction agents
├── CHANGELOG.md
├── CITATION.cff
├── .zenodo.json
├── LICENSE
├── mkdocs.yml
├── pyproject.toml
├── uv.lock
├── csag/              # command-line interface and Python API
├── skills/            # two skills, authoritative LinkML schema, generated JSON Schema
├── schema/            # generated Markdown schema documentation
├── scripts/           # checks, figure generation, and the local OCR helper
├── docs/              # MkDocs documentation
├── examples/          # redistributable example artifacts and manifests
├── tests/             # test suite and fixtures
└── supplementary/     # entity-normalization supplement
```

MkDocs builds the documentation site from `mkdocs.yml`, with `docs/index.md`
as the entry point. [docs/release-process.md](docs/release-process.md)
describes the release procedure.

## Citing

Cite two works when CSAG contributes to a project: the CSAG concept manuscript
(in preparation) for the schema and argumentation model, and the software
release recorded in `CITATION.cff` (version 1.0.0) for the exact validator,
schema, command-line, example, and export behavior used.
`scripts/record_archive_doi.py` replaces the `pending-zenodo-doi` placeholder
in the release metadata with the archive DOI.

## License

The schema, scripts, documentation, and examples are released under the BSD
3-Clause License; `LICENSE` holds the license text and the Berkeley Lab
copyright notice (Copyright (c) 2026, The Regents of the University of
California, through Lawrence Berkeley National Laboratory). Source manuscripts
and third-party PDFs keep their own licenses, recorded in each example manifest
and in [docs/license-policy.md](docs/license-policy.md).
