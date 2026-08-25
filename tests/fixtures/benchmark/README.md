# Benchmark fixture

This directory contains a minimal benchmark package:

- `answer_key.hidden.json` - reference CSAG used as the scoring key.
- `participant_output.json` - example participant submission.
- `scoring_schema.json` - partial-credit weights, false-positive penalty, and disagreement note.
- `scoring_schema.invalid_missing_disagreement.json` - negative schema fixture that must be rejected.
- `scored_report.json` - expected report from `csag score`.

Regenerate the scored report with:

```bash
uv run csag score \
  --answer-key tests/fixtures/benchmark/answer_key.hidden.json \
  --participant tests/fixtures/benchmark/participant_output.json \
  --scoring-schema tests/fixtures/benchmark/scoring_schema.json \
  --report-out tests/fixtures/benchmark/scored_report.json
```

Verify the stored report against the current scorer:

```bash
uv run python scripts/check_benchmark_report.py
```

The scorer validates both artifacts, matches assertions independently of local
IDs, and scores resolved context, grounding, and evidence content. The stored
report includes the scorer version and SHA-256 hashes of all three inputs.
