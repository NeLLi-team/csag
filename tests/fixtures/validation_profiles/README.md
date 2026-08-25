# Validation profile fixtures

These fixtures exercise the three strictness profiles. Module profile aliases
(`core`, `bio`, `reasoning`, and `benchmark`) are covered by the CLI tests
because they report module intent and warning-level enrichment checks.

| Fixture | Expected result | Purpose |
|---------|-----------------|---------|
| `paper_local.valid.json` | pass | Baseline local paper extraction. |
| `paper_local.invalid_missing_context.json` | fail | Enforces the assertion context invariant. |
| `paper_local.invalid_misplaced_semantics.json` | fail | Enforces placement of polarity, relation, and reasoning fields. |
| `paper_local.invalid_missing_dataset.json` | fail | Enforces dataset extraction when data-availability signals are present. |
| `paper_local.invalid_missing_artifact.json` | fail | Enforces artifact extraction when figure/table captions are present. |
| `promoted_claim.valid.json` | pass | Checks curation fields, evidence rationale, and grounding. |
| `promoted_claim.invalid_missing_rationale.json` | fail | Enforces promoted evidence-link rationale. |
| `promoted_claim.invalid_missing_curation_status.json` | fail | Enforces human curation status before promotion. |
| `promoted_claim.invalid_missing_review_provenance.json` | fail | Enforces promotion review provenance. |
| `benchmark_key.valid.json` | pass | Checks benchmark evidence strength for core claims. |
| `benchmark_key.invalid_weak_core.json` | fail | Rejects weak evidence for a core benchmark claim. |

Expected reports are stored in `reports/`.

Verify that expected reports still match the current validator:

```bash
uv run python scripts/check_validation_profile_reports.py
```

When validator behavior changes, regenerate the expected reports
with:

```bash
uv run python scripts/check_validation_profile_reports.py --update
```
