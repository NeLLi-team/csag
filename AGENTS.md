# AGENTS.md

This file is the operating contract for an agent that produces a CSAG from one
manuscript in this repository.

## Inputs

Accept a PDF, a Markdown file with a `# Title` line and recognizable section
headings, or a work directory that already holds a manuscript and sidecars
(run `uv run csag inspect <dir>` to see its state and the next command).

## Procedure

Use one work directory per manuscript. The directory is your choice; the
commands use `work/<stem>/` for a manuscript named `<stem>`, and git ignores
`work/`. Run every command from the repository root with `uv run`.

1. Run `csag ingest <input> --output-dir work/<stem>/`. It writes the Markdown
   and the article sidecars. For a PDF, add the conversion mode:
   `--pdf-mode ocr` (OCR API; needs `OCR_API_KEY` or `NELLI_API_KEY`),
   `--pdf-mode local` (LiteParse; needs the `local-pdf` extra), or
   `--pdf-mode auto` (OCR API, then LiteParse).
2. Run `csag scaffold work/<stem>/<stem>.md --article-json
   work/<stem>/<stem>.article.json --output work/<stem>/paper_extraction.json
   --profile lite` to write a draft extraction.
3. Run `csag inspect work/<stem>/` to see the state of the work directory and
   the next command.
4. Curate `paper_extraction.json` by hand: read `<stem>.md` and
   `<stem>.article.json` and follow `skills/csag-extraction/SKILL.md`. The
   scaffold is a draft, not an extraction.
5. Run `csag validate work/<stem>/paper_extraction.json --source-markdown
   work/<stem>/<stem>.md --article-json work/<stem>/<stem>.article.json
   --profile lite --report-out work/<stem>/paper_extraction.validation.json`.
   Use `--profile paper_local` for a full extraction.
6. Run `csag report work/<stem>/paper_extraction.json --source-markdown
   work/<stem>/<stem>.md --article-json work/<stem>/<stem>.article.json
   --report-out work/<stem>/paper_extraction.quality.json --strict`.
7. Run `csag lint work/<stem>/paper_extraction.json --report-out
   work/<stem>/paper_extraction.lint.json --strict`.
8. Run `csag export work/<stem>/paper_extraction.json --format ro-crate
   --output work/<stem>/ro-crate` to bundle the extraction with its source
   files and reports.

The work directory then holds:

```text
work/<stem>/<stem>.md
work/<stem>/<stem>.section_audit.json
work/<stem>/<stem>.article.json
work/<stem>/paper_extraction.json
work/<stem>/paper_extraction.validation.json
work/<stem>/paper_extraction.quality.json
work/<stem>/paper_extraction.lint.json
```

Reports record SHA-256 hashes of their inputs. After you change
`paper_extraction.json`, rerun steps 5 to 7.

## Where the rules live

- `skills/pdf-to-md/SKILL.md`: the two conversion engines, the article
  sidecar, and how to shape LiteParse output before you continue.
- `skills/csag-extraction/SKILL.md`: the structural invariants, the coverage
  targets, the identifier conventions, and the validation profiles.
- `skills/csag-extraction/references/CSAG_PLAYBOOK.md`: what each class
  captures and how to handle edge cases.

## Quality gate before stopping

Fix the extraction, not the reports, until all of these hold:

- `csag validate` prints `OK` for the profile in use.
- `csag report --strict` exits 0 with an empty `issues` list.
- `csag lint --strict` exits 0.
- Every category the manuscript lacks, such as a dataset or a stated
  hypothesis, is recorded in `notes`.

## Failure modes to avoid

- Extracting only the sentences that match the retrieval keywords. Extract the
  full manuscript.
- Delivering one assertion and one evidence link when the manuscript supports
  more.
- Recording support or refute polarity anywhere other than an evidence link.
- Inventing field values or text-span offsets the manuscript does not contain.
- Stopping after `paper_extraction.json` without validation, quality report,
  and lint.
