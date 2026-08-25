# CSAG Lite example

This directory holds a minimal CSAG Lite artifact: one assertion with one
embedded context, one evidence item, one evidence link, and grounded text
spans. Validate it with the `lite` profile and build its quality report with
the `lite` document scope:

```bash
uv run csag validate examples/lite/paper_extraction.json \
  --source-markdown examples/lite/lite.md \
  --article-json examples/lite/lite.article.json \
  --profile lite \
  --report-out /tmp/lite.validation.json

uv run csag report examples/lite/paper_extraction.json \
  --source-markdown examples/lite/lite.md \
  --article-json examples/lite/lite.article.json \
  --document-scope lite \
  --report-out /tmp/lite.quality.json
```
