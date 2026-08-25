# Article schema

The article JSON is the structured interface between PDF or Markdown ingestion
and CSAG extraction. It applies whenever the source is a scientific manuscript.

## Output shape

One JSON object with these keys and no other top-level fields:

```json
{
  "title": "",
  "authors": "",
  "affiliations": "",
  "abstract": "",
  "main": "",
  "methods": "",
  "figure_legends": [],
  "figure_interpretation": "",
  "references": []
}
```

## Field semantics

| Key | Content |
|-----|---------|
| `title` | Manuscript title exactly as written. |
| `authors` | Author list as one comma-separated string. |
| `affiliations` | Affiliations as one comma-separated string. |
| `abstract` | Abstract text verbatim when present. |
| `main` | Narrative body: introduction, results, discussion, and conclusion in reading order. |
| `methods` | Methods or Materials section text only. |
| `figure_legends` | One entry per figure or table caption. |
| `figure_interpretation` | Short interpretation of figures and tables, grounded in captions and direct figure review. |
| `references` | One entry per cited reference. |

## Extraction rules

- Prefer fidelity over rewriting.
- Keep headings and section order when they help preserve structure.
- Deduplicate page headers, footers, and page numbers before structuring.
- Do not invent missing sections.
- When a section is absent, leave the field empty (`""` or `[]`); do not fill
  it with unrelated text.

## Minimum content

For a scientific manuscript, `title`, `authors`, and `main` are non-empty.
`affiliations`, `abstract`, `methods`, `figure_legends`, and `references` are
populated when the source contains them.

## Validation

`$SKILL_DIR/scripts/validate_article_json.py`, where `SKILL_DIR` is the
`pdf-to-md` skill directory, checks:

- the exact top-level key set
- the type of each value (string, or list of strings)
- non-empty `title`, `authors`, and `main` with `--scientific-paper`
- consistency with the section audit (`--section-audit`, default
  `<stem>.section_audit.json` next to the article JSON); with
  `--scientific-paper` the audit is required

The LinkML (Linked Data Modeling Language) shape is in
`references/article.yaml`.
