# Evaluation metrics

All four metric families are planned; this repository publishes no results for
them. Each family tests whether a CSAG changes a downstream scientific outcome
compared with a prose baseline (the same manuscript read as text, or a
free-text rubric), so a future difference is reported as a delta.

## Human-audit time

This family measures whether a CSAG lets a curator find unsupported or weakly
grounded core and major assertions faster than reading prose, without losing
recall. Curators audit matched manuscripts in two conditions, prose and CSAG,
with condition order counterbalanced. The record per manuscript is the median
time-to-decision and the set of unsupported or weakly grounded assertions each
curator flags, scored against a curated reference set.

A CSAG meets the planned target when it satisfies either row:

| Planned target | Condition |
|----------------|-----------|
| Median review time reduced by at least 25% | At equal or better unsupported-claim recall |
| Unsupported-claim recall improved by at least 20 percentage points | At equal review time |

## Unsupported-claim detection

This family measures how well a CSAG-assisted review identifies unsupported or
weakly supported claims, weighting core and major assertions more than minor
ones. Evaluators compare flagged claims with a curated reference of unsupported
and weakly supported claims and report precision, recall, and F1.
Severity-weighted recall weights each missed claim by its criticality. The
false-positive rate is tracked against the prose-review baseline on the same
manuscripts.

| Metric | Planned target |
|--------|----------------|
| Severity-weighted recall (core and major unsupported claims) | At least 0.85 |
| False-positive rate compared with the prose-review baseline | No more than 10 percentage points higher |

## Scoring reproducibility

This family measures whether evaluation results are stable across evaluators
and across repeated runs, so that a CSAG score means the same thing each time.
Multiple evaluators score the same artifacts and report inter-rater agreement.
The deterministic CSAG scorer runs repeatedly on the same inputs and is checked
for bit-identical results. The variance of CSAG scores is compared with the
variance of a free-text rubric applied to the same material.

| Metric | Planned target |
|--------|----------------|
| Inter-rater agreement | At least 0.8 |
| Deterministic CSAG scorer | Identical results on repeated runs |
| Score variance | Lower than a free-text rubric |

## Handoff success

This family measures whether a human or agent can resume a scientific task from
a CSAG more effectively than from a prose handoff. Participants receive a
partially completed task plus either a CSAG handoff or a prose handoff, with
task and order counterbalanced. The record is the count of repeated failed
paths (re-deriving or re-checking work the handoff settled) and whether the
next action taken is correct against a reference.

| Metric | Planned target |
|--------|----------------|
| Repeated failed paths | Reduced by at least 30% |
| Next-action correctness | Improved by at least 20 percentage points |
