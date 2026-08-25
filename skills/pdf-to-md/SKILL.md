---
name: pdf-to-md
description: >-
  Convert any PDF (or DOCX/PPTX/XLSX/image) to clean Markdown. For scientific
  papers, produce the canonical pdf-to-md bundle (Markdown plus section_audit.json
  and article.json) using the remote OCR API when an OCR key is available, or
  LiteParse v2 locally when it is not. For any non-paper PDF, defer to a fast,
  local, no-API-key LiteParse v2 conversion. Use when turning a PDF or manuscript
  into Markdown, extracting article structure, or preparing input for csag-extraction.
license: BSD-3-Clause
metadata:
  version: "1.0.0"
---

# pdf-to-md

Convert a PDF to Markdown. For a scientific manuscript, produce the full
manuscript bundle (Markdown, section audit, and article JSON) that
`csag-extraction` reads. For any other PDF (reports, slides, letters, forms),
produce plain Markdown and stop.

`SKILL_DIR` is the directory that contains this `SKILL.md`; in the CSAG
repository it is `skills/pdf-to-md`. Set it once, then run every script as
`uv run "$SKILL_DIR/scripts/<name>"`:

```bash
SKILL_DIR=skills/pdf-to-md
```

The output directory (`--output-dir`) is the caller's choice. In the CSAG
repository the convention is a work directory such as `work/<stem>/`, which
git does not track. The examples in this file write to `out/`.

## Engines

Two engines convert a PDF to Markdown. For input stem `<stem>`, both write
`<stem>.md`, `<stem>.ocr.json`, and `<stem>.job.json` to the output directory.

The OCR (optical character recognition) API engine, `ocr_api_job.py`, submits
the PDF to a remote service with `curl` and needs `OCR_API_KEY` or
`NELLI_API_KEY` (or `--api-key`). The default endpoint is
https://api.newlineages.com/ocr; override it with `OCR_BASE_URL` or
`--base-url`. The base URL must use HTTPS, or HTTP on localhost. This engine
gives higher layout fidelity than LiteParse and needs little manual shaping.

The LiteParse v2 engine, `liteparse_to_md.py`, runs locally with no key. It
uses [run-llama/liteparse](https://github.com/run-llama/liteparse), the Rust
rewrite with the `LiteParse` Python API and `lit` CLI; LiteParse v1 is a
different, unsupported API. The script declares `liteparse>=2,<3` as a PEP 723
inline dependency and refuses any other version, so `uv run` installs the
matching per-platform binary from the wheel. OCR is on by default (bundled
Tesseract); pass `--no-ocr` for text-based PDFs. LiteParse is a mechanical
parser. It has no native Markdown, infers headings from font size and weight,
and leaves artifacts (split words, broken hyphenation, dropped author blocks,
merged columns). Its output is a draft that you shape before you hand it on
(see "Shape the LiteParse output").

## Choose the output and the engine

Check whether a key is set without printing it:

```bash
test -n "${OCR_API_KEY:-}${NELLI_API_KEY:-}" && echo "OCR API key set" || echo "no OCR API key"
```

| Document | OCR API key | Output | Engine |
|----------|-------------|--------|--------|
| Scientific manuscript | set | full manuscript bundle | OCR API |
| Scientific manuscript | not set | full manuscript bundle | LiteParse v2 |
| Any other PDF | set or not set | plain Markdown | LiteParse v2 |

A scanned or layout-heavy manuscript without a key converts with LiteParse
v2, which runs OCR locally, but layout fidelity is lower than with the OCR
API.

## Full manuscript bundle

For input `paper.pdf` (stem `paper`), the bundle in `out/` is `out/paper.md`,
`out/paper.section_audit.json`, and `out/paper.article.json`. Step 4 adds
`out/figure_review/`.

1. Convert to Markdown with the OCR API:

    ```bash
    uv run "$SKILL_DIR/scripts/ocr_api_job.py" paper.pdf --output-dir out
    ```

    or with LiteParse v2:

    ```bash
    uv run "$SKILL_DIR/scripts/liteparse_to_md.py" paper.pdf --output-dir out
    ```

    When LiteParse was the engine, shape `out/paper.md` before you continue
    (see "Shape the LiteParse output"); the later steps read that Markdown.

2. Build the section audit:

    ```bash
    uv run "$SKILL_DIR/scripts/build_section_audit.py" out/paper.md
    ```

3. Populate the first-pass article JSON (this step also writes the audit):

    ```bash
    uv run "$SKILL_DIR/scripts/populate_article_json.py" out/paper.md
    ```

    The heuristics miss authors with superscripts, methods, references, and
    figure interpretation. Review and complete those fields against the
    Markdown and `references/article_schema.md`.

4. When the manuscript has figure or table captions, render the pages, then
   fill `figure_interpretation` from the captions and the rendered pages:

    ```bash
    uv run "$SKILL_DIR/scripts/render_pdf_pages_to_png.py" paper.pdf --output-dir out/figure_review
    ```

5. Validate against the schema and the section audit:

    ```bash
    uv run "$SKILL_DIR/scripts/validate_article_json.py" out/paper.article.json \
      --scientific-paper --section-audit out/paper.section_audit.json
    ```

    Resolve every reported error before you stop. When a field is empty
    because the source has no such content, confirm the absence; do not invent
    content.

To start from a Markdown file you already trust, skip step 1 and run steps 2
to 5 on that file.

## Plain Markdown

One local step, no key:

```bash
uv run "$SKILL_DIR/scripts/liteparse_to_md.py" report.pdf --output-dir out --no-ocr
```

Other options: `--ocr-server-url URL` (an HTTP OCR server for higher
accuracy), `--ocr-language eng`, `--target-pages "1-5,10"`, `--max-pages N`,
`--dpi DPI`, and `--password PW`. The converter detects the title and section
headings from font size and weight, filters page furniture (watermarks,
running headers, repeated footers), and reflows text into paragraphs. Shape
the result before you hand it on.

## Shape the LiteParse output

Read `<stem>.md` against the rendered pages and fix what the heuristics
cannot. Do not hand back raw script output.

- Confirm that the `# ` heading is the real title, not a journal banner, DOI
  line, or "Downloaded from" watermark; set it when it is wrong or missing.
- Promote section headings the font heuristic missed (`## Abstract`,
  `## Introduction`, `## Methods`, `## Results`, `## Discussion`,
  `## References`) and demote false positives; keep reading order.
- Rejoin words split mid-token (for example "Berke ley" to "Berkeley") and
  fix hyphenation that did not rejoin across line breaks.
- Reconstruct the author list and affiliations, which LiteParse often drops or
  scrambles around superscripts and email addresses.
- Keep one figure or table caption per block; rebuild simple tables that
  collapsed into runs of text.
- Delete leftover running headers, page numbers, and license boilerplate.
- Make each reference its own entry, not one merged block.

For the full manuscript bundle, run `populate_article_json.py` after this
cleanup, then complete every `article.json` field the first pass leaves empty
(`authors`, `affiliations`, `methods`, `references`, `figure_interpretation`)
from the shaped Markdown and the rendered pages. Do not invent content to pass
validation. For plain Markdown, the shaped Markdown is the deliverable.

## Quick reference

| Task | Command |
|------|---------|
| Manuscript, key set | `ocr_api_job.py paper.pdf --output-dir out` |
| Manuscript, no key | `liteparse_to_md.py paper.pdf --output-dir out` |
| Any PDF, plain Markdown | `liteparse_to_md.py report.pdf --output-dir out --no-ocr` |
| Section audit | `build_section_audit.py out/paper.md` |
| Article JSON | `populate_article_json.py out/paper.md` |
| Figure PNGs | `render_pdf_pages_to_png.py paper.pdf --output-dir out/figure_review` |
| Validate the bundle | `validate_article_json.py out/paper.article.json --scientific-paper --section-audit out/paper.section_audit.json` |

Run each script as `uv run "$SKILL_DIR/scripts/<name>"`. `liteparse_to_md.py`
and `render_pdf_pages_to_png.py` declare PEP 723 inline dependencies
(`liteparse`; `pypdfium2` and `pillow`) that `uv run` installs; the other
scripts use only the standard library.

## Inputs

- A PDF, or a format that LiteParse converts to PDF first (DOCX, PPTX, XLSX,
  ODT, and CSV through LibreOffice; JPG, PNG, and TIFF through ImageMagick).
- To start from Markdown: a `.md` file with a `# Title`, an author and
  affiliation block, recognizable section headings (Abstract, Introduction,
  Methods, Results, Discussion, Conclusion, References), and figure or table
  captions that start with `Fig.`, `Figure`, or `Table`.
- For the OCR API engine: `OCR_API_KEY` or `NELLI_API_KEY`, and `curl`.
- A writable `--output-dir`.

## Outputs

- Plain Markdown: `<stem>.md`, plus `<stem>.ocr.json` and `<stem>.job.json`
  as provenance.
- Full manuscript bundle: the same files plus `<stem>.section_audit.json` and
  `<stem>.article.json`, and `figure_review/` PNGs when rendered.
  `csag-extraction` reads `<stem>.md` and `<stem>.article.json`; the other
  files are provenance.
- The article JSON has exactly these keys: `title`, `authors`,
  `affiliations`, `abstract`, `main`, `methods`, `figure_legends` (list),
  `figure_interpretation`, `references` (list). See
  `references/article_schema.md` and `references/article.yaml`.

## Quality gates

- The engine is the OCR API or LiteParse v2; with LiteParse, `<stem>.job.json`
  records a `tool_version` of 2.x.
- When LiteParse was the engine, the Markdown has been shaped (title,
  headings, rejoined words, front matter, captions, references).
- Plain Markdown is non-empty, has a sensible `#` title or none (never a
  watermark), and contains no repeated page furniture.
- For the bundle, `validate_article_json.py --scientific-paper` prints `OK`.
- `title`, `authors`, and `main` are populated for a real manuscript, or their
  absence is confirmed against the source.
- When figure or table captions exist, `figure_legends` is populated and
  `figure_interpretation` is filled, or a note records that no interpretation
  was possible.
- `<stem>.job.json` records the engine, tool version, and OCR setting.

## Examples

Plain Markdown from a report:

```bash
uv run "$SKILL_DIR/scripts/liteparse_to_md.py" report.pdf --output-dir out --no-ocr
```

This writes `out/report.md`, `out/report.ocr.json`, and `out/report.job.json`.

Full manuscript bundle without an OCR API key:

```bash
uv run "$SKILL_DIR/scripts/liteparse_to_md.py" paper.pdf --output-dir out
uv run "$SKILL_DIR/scripts/populate_article_json.py" out/paper.md
uv run "$SKILL_DIR/scripts/validate_article_json.py" out/paper.article.json \
  --scientific-paper --section-audit out/paper.section_audit.json
```

## Troubleshooting

- `liteparse is not installed`: run the script with `uv run`, not
  `uv run python`, so that `uv` reads the PEP 723 inline dependency. Offline,
  run `pip install 'liteparse>=2,<3'` first.
- `pdf-to-md requires LiteParse v2`: a v1 or other non-v2 `liteparse` is
  installed. Reinstall with `pip install 'liteparse>=2,<3'`.
- The title is a journal banner, watermark, or "Downloaded from" line: the
  converter filters furniture and repeated headers. When one slips through,
  remove it from the Markdown before step 2; `article_extraction.py` also
  re-derives the title from the body.
- `authors`, `methods`, or `references` is empty for a real manuscript: the
  first-pass heuristics miss superscript-heavy author lines and short note
  formats. Fill the fields by hand from the Markdown; this is expected, not a
  converter failure.
- A scanned or image-only PDF yields little text: keep OCR enabled (the
  default) and raise `--dpi`, or point `--ocr-server-url` at an EasyOCR or
  PaddleOCR server. The OCR API engine gives higher fidelity.
- `Missing OCR API key`: set `OCR_API_KEY` or `NELLI_API_KEY`, or use the
  LiteParse v2 engine.
- Garbled equations or merged columns: LiteParse is the fast path; for
  layout-heavy manuscripts prefer the OCR API engine.
