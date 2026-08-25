# Schema artifacts

The authoritative CSAG schema is the LinkML (Linked Data Modeling Language)
source `skills/csag-extraction/assets/csag.yaml`.

This directory contains generated files:

- `csag.md`: Markdown reference of the controlled vocabularies and classes.
- `README.md`: this file.

The generated JSON Schema files sit next to the LinkML source in
`skills/csag-extraction/assets/`:

- `csag.schema.json`: closed JSON Schema for `PaperExtraction`.
- `csag.handoff.schema.json`: closed JSON Schema for `HandoffEnvelope`.

Regenerate every generated file with:

```bash
uv run python scripts/generate_schema_artifacts.py
```

Check that the committed files match the generator with:

```bash
uv run python scripts/check_schema_artifacts.py
```
