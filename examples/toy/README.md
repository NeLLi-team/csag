# Toy example

This synthetic manuscript is small enough to inspect by hand. Its CSAG shows
the minimum extraction shape: assertions with contexts, one evidence item, one
evidence link, one inference, one critique, one knowledge gap, and one
dataset.

## Files

- `toy.md`: source Markdown manuscript
- `toy.section_audit.json`: section audit
- `toy.article.json`: article sidecar
- `paper_extraction.json`: the CSAG
- `paper_extraction.validation.json`: validator report
- `paper_extraction.quality.json`: quality report
- `toy_measurements.tsv`: data file referenced by the dataset object
- `example_manifest.json`: source, license, included files, and
  interpretation

## Interpretation

The manuscript makes a treatment-control claim: blue-light cultures show
higher plastid pigment absorbance than dark controls. The CSAG separates the
conclusion from the measurement that supports it and records the replication
limitation as both a critique and a knowledge gap.

## Quick check

Validate the CSAG with the `paper_local` profile and rebuild the quality
report:

```bash
uv run csag validate examples/toy/paper_extraction.json \
  --source-markdown examples/toy/toy.md \
  --article-json examples/toy/toy.article.json \
  --profile paper_local \
  --report-out examples/toy/paper_extraction.validation.json

uv run csag report examples/toy/paper_extraction.json \
  --source-markdown examples/toy/toy.md \
  --report-out examples/toy/paper_extraction.quality.json
```
