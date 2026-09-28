# Changelog

## Unreleased

- `paper_local` validation accepts a Dataset without an accession, repository,
  or URL when its own TextSpan quotes a positive statement that the data are
  available on request.
- The quality report gives each claim readout a `qa_status`: the
  `CSAG_QA_01_STATUS` answer computed from the strength-weighted evidence
  links.
- The `csag-extraction` skill states where `SKILL_DIR` points for an installed
  copy.

## 1.0.0 - 2026-08-25

First public release. It contains:

- the LinkML (Linked Data Modeling Language) schema with generated JSON Schema
  files and Markdown documentation
- the `csag` command line with the `ingest`, `validate`, `report`, `scaffold`,
  `inspect`, `export`, `lint`, `score`, `doctor`, `check-examples`, and
  `quickstart` commands
- the `pdf-to-md` and `csag-extraction` skills
- validation profiles
- worked examples with three CC BY source PDFs
