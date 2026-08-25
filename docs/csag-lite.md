# CSAG Lite

CSAG Lite is the smallest useful subset of a Conditional Scientific
Argumentation Graph (CSAG). It records what a manuscript claims, the evidence
the manuscript offers, and how each piece of evidence bears on each assertion.
Every assertion has a context, and every assertion and evidence item is
grounded to a text span. A Lite artifact is valid on its own and small enough
to write or review by hand.

## Staged workflow

The `csag` command drafts and checks a Lite artifact in seven stages. Run the
commands from the repository checkout. The commands write to `work/paper/`;
the work directory is your choice. Keep every file of one manuscript in the
same work directory, because later stages find their inputs by name.

1. Ingest the manuscript. The input is a PDF or a Markdown file. The output is
   canonical Markdown plus the `article.json` and `section_audit.json`
   sidecars.

    ```bash
    uv run csag ingest manuscript.md --output-dir work/paper/
    ```

    For a PDF, pick a conversion mode with `--pdf-mode`: `ocr` sends the PDF
    to the OCR (optical character recognition) API, `local` converts it with
    LiteParse, and `auto` tries the OCR API first when a key is available and
    falls back to LiteParse. The OCR API needs a key in `OCR_API_KEY` or
    `NELLI_API_KEY`; LiteParse needs the `local-pdf` extra
    (`uv sync --extra local-pdf`).

    ```bash
    uv run csag ingest paper.pdf --output-dir work/paper/ --pdf-mode auto
    ```

2. Scaffold a draft `paper_extraction.json` from the Markdown and the article
   sidecar.

    ```bash
    uv run csag scaffold work/paper/manuscript.md \
      --article-json work/paper/manuscript.article.json \
      --output work/paper/paper_extraction.json \
      --profile lite
    ```

    Edit the draft: replace the `TODO` placeholders and add the manuscript's
    assertions, evidence items, and evidence links. The extraction rules are
    in `skills/csag-extraction/SKILL.md`.

3. Inspect the work directory. The command lists which files are present and
   prints the next command to run.

    ```bash
    uv run csag inspect work/paper/
    ```

4. Validate the extraction with the `lite` profile.

    ```bash
    uv run csag validate work/paper/paper_extraction.json \
      --source-markdown work/paper/manuscript.md \
      --article-json work/paper/manuscript.article.json \
      --profile lite \
      --report-out work/paper/paper_extraction.validation.json
    ```

5. Build the quality report with the `lite` document scope.

    ```bash
    uv run csag report work/paper/paper_extraction.json \
      --source-markdown work/paper/manuscript.md \
      --article-json work/paper/manuscript.article.json \
      --document-scope lite \
      --report-out work/paper/paper_extraction.quality.json
    ```

6. Lint the stable IDs and the grounding.

    ```bash
    uv run csag lint work/paper/paper_extraction.json \
      --report-out work/paper/paper_extraction.lint.json
    ```

7. Export the artifact. Canonical JSON and RO-Crate (Research Object Crate)
   are lossless; [Interoperability](interoperability.md) describes the other
   formats. The RO-Crate output directory must be empty or not exist.

    ```bash
    uv run csag export work/paper/paper_extraction.json \
      --format ro-crate --output work/paper-ro-crate
    ```

Validation, quality, and lint reports record SHA-256 hashes of their inputs.
After an input changes, `csag inspect` reports the affected report as stale
and prints the command that refreshes it.

## The Lite object set

A Lite artifact uses six classes.

| Class | What it records |
|-------|-----------------|
| `PaperExtraction` | The root document: identity and version metadata (`id`, `title`, `schema_version`, `validator_version`) and the assertion, evidence item, and evidence link arrays. |
| `TextSpan` | A pointer into the source Markdown (document, section, character offsets, exact text) that grounds an assertion or an evidence item. |
| `Assertion` | One claim the manuscript makes, in natural language, with a `claim_role` and a `normalization_status`. |
| `Context` | The scope under which an assertion or evidence item holds, such as the organism, cell type, or model system. |
| `EvidenceItem` | An observation or result the manuscript reports as evidence, with its own contexts when needed. |
| `EvidenceLink` | A typed connection from an evidence item to an assertion with a `polarity` of `supports`, `refutes`, `mixed`, or `inconclusive`. |

The `lite` profile does not check any other class, such as artifacts,
datasets, entities, studies, experiments, inference steps, assertion relations,
critiques, knowledge gaps, and QA items. Add such objects when the source
supports them and a downstream task needs them. [Validation
profiles](profiles.md) lists which module each class belongs to.

## What the `lite` profile requires

The `lite` profile checks structure and grounding. It does not require
curated criticality, falsification criteria, or extraction activities. It
requires that:

- the root `PaperExtraction` has `id`, `title`, `schema_version`, and
  `validator_version`, and the `assertions`, `evidence_items`, and
  `evidence_links` arrays;
- the artifact contains at least one context, one assertion, one evidence
  item, and one evidence link;
- every assertion has an `id`, `assertion_text`, a valid `claim_role`, a
  valid `normalization_status`, at least one context whose ID resolves to a
  context in the same artifact, and at least one text span;
- every evidence item has an `id` and at least one text span;
- every evidence link has an `id`, an `evidence_item` reference, an
  `assertion` reference, and a valid `polarity`, and both references resolve.

## Worked example

A complete, valid Lite artifact is in `examples/lite/`. Validate it with:

```bash
uv run csag validate examples/lite/paper_extraction.json \
  --source-markdown examples/lite/lite.md \
  --article-json examples/lite/lite.article.json \
  --profile lite \
  --report-out /tmp/lite.validation.json
```
