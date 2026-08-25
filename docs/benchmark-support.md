# Benchmark answer keys and scoring

A benchmark package contains:

- the answer key, a hidden reference CSAG validated with the `benchmark_key`
  profile (or `core,benchmark`);
- the participant extraction;
- a scoring schema with the allowed equivalent formulations, the false-positive
  penalty, partial-credit rules, and an expert-disagreement note;
- the scored report.

Partial credit distinguishes missing evidence, unsupported assertions, wrong
polarity, missing context, missing text spans, and hallucinated assertions.
An answer key is a curated interpretation, not the only defensible reading of a
manuscript, so the scoring schema records an expert-disagreement note, and
`csag score` rejects a scoring schema without one.

The fixture in `tests/fixtures/benchmark/` includes every piece:

- `answer_key.hidden.json`
- `participant_output.json`
- `scoring_schema.json`
- `scoring_schema.invalid_missing_disagreement.json`, a negative fixture that
  lacks the expert-disagreement note
- `scored_report.json`

## Scoring

Before scoring, `csag score` validates the answer key with `benchmark_key` and
the participant extraction with `paper_local`. Both artifacts identify the same
manuscript and contain resolvable references. Assertions match by normalized
canonical text or a curator-approved equivalent formulation, not by local
object ID. Each participant assertion matches at most one answer-key
assertion, each answer-key assertion keeps its best-scoring match, and
unmatched participant assertions count as false positives.

The four score components compare content:

- assertion text: the canonical or approved equivalent formulation;
- context: the semantic `Context` fields, excluding IDs and provenance;
- grounding: document IDs, sections, character offsets, and exact text;
- evidence: polarity together with normalized `EvidenceItem` text and resolved
  source spans; when spans are present, both the interpretation text and the
  spans agree.

The report records the scorer version, SHA-256 hashes for all inputs, the
matched participant assertion, the match basis, and weighted component scores.
Invalid artifacts produce an error report without a numeric score.

Run the scorer:

```bash
uv run csag score \
  --answer-key tests/fixtures/benchmark/answer_key.hidden.json \
  --participant tests/fixtures/benchmark/participant_output.json \
  --scoring-schema tests/fixtures/benchmark/scoring_schema.json \
  --report-out tests/fixtures/benchmark/scored_report.json
```

Check that the stored scored report matches the scorer:

```bash
uv run python scripts/check_benchmark_report.py
```

After a scoring change, regenerate the stored report:

```bash
uv run python scripts/check_benchmark_report.py --update
```
