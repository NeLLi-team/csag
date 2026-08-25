# Validation profiles

A module is a group of schema classes: `core`, `bio`, `reasoning`,
`research_state`, or `benchmark`. A profile is the value passed to
`csag validate --profile`: one of the strictness profiles `lite`,
`paper_local`, `promoted_claim`, and `benchmark_key`; one or more modules in a
comma list such as `core,bio`; or `handoff` for a `HandoffEnvelope`. The
validation report records the strictness profile and the selected modules.
Failures in any profile are blocking. The report records `ok: false`, and the
artifact is incomplete or cannot be traversed reliably.

## Modules

| Module | Purpose | Main classes |
|--------|---------|--------------|
| `core` | Manuscript-local claim, evidence, grounding, critique, gap, dataset, and provenance ledger. | `PaperExtraction`, `TextSpan`, `Assertion`, `Context`, `EvidenceItem`, `EvidenceLink`, `StudyCritique`, `KnowledgeGap`, `Artifact`, `Dataset`, provenance fields |
| `bio` | Biological normalization and study or assay enrichment. | `Entity`, `EntityMention`, `OntologyAnnotation`, `Condition`, `Qualifier`, `Study`, `Experiment`, `Variable`, normalized assertion fields |
| `reasoning` | Derived reasoning structure over core claims. | `InferenceStep`, `AssertionRelation` |
| `research_state` | Manuscript-local review annotations around claims. | `ResearchStateRecord`, `NextAction`, `Execution` |
| `benchmark` | Answer-key and scoring surface. | `QAItem`, `Answer`, assertion criticality, falsification criteria, curated evidence strength, scoring metadata |

`core` is mandatory, and every profile checks it. The other modules are
optional enrichment layers, and selecting one adds warnings, not errors. For
example, `core,bio` checks the core artifact and warns when no biological
enrichment is populated. A non-biological manuscript or an early extraction
stays valid, and the report shows which modules the curator intended.

The `reasoning` module is separate from `core` because inference steps and
claim-to-claim relations (`qualifies`, `contradicts`, `competes_with`,
`alternative_to`, `merged_into`, `replicates`) often need curator judgment or
cross-manuscript synthesis. A raw extraction does not have to carry them, and
they are not author-stated evidence.

The `research_state` module records a manuscript-local read on a claim, a
suggested next action, or a run described in the manuscript. Support and refute
polarity stays on `EvidenceLink`. Exchange between agents, revision lineage,
ownership, execution provenance, and conflict resolution belong in the separate
[`HandoffEnvelope`](handoff-envelope.md) root, which references content-hashed
`PaperExtraction` snapshots instead of changing them.

Select modules with a comma list:

```bash
uv run csag validate paper_extraction.json \
  --profile core,bio \
  --report-out paper_extraction.validation.json
```

## Strictness profiles

| Profile | Modules | Use |
|---------|---------|-----|
| `lite` | `core` (Lite subset) | First draft of an extraction. |
| `paper_local` | `core` | Complete extraction from one manuscript. |
| `promoted_claim` | `core` plus curation requirements | Claims ready for reuse outside the source manuscript. |
| `benchmark_key` | `core,benchmark` plus curation and evidence-strength requirements | Answer keys for scoring. |

`candidate` is an alias of `paper_local`, and `ground_truth` is an alias of
`benchmark_key`. A module list without a strictness profile validates at
`paper_local` strictness; a list that includes `benchmark` validates at
`benchmark_key` strictness.

### `lite`

`lite` is the default profile of `csag scaffold` and the recommended starting
point for an extraction; `csag validate` defaults to `paper_local`. `lite`
checks the Lite subset (`PaperExtraction`, `TextSpan`, `Assertion`, `Context`,
`EvidenceItem`, `EvidenceLink`) and skips the extraction-activity and
source-consistency requirements of `paper_local`. [CSAG Lite](csag-lite.md)
lists what `lite` requires. Move to `paper_local`, `promoted_claim`, or
`benchmark_key` as the artifact matures.

### `paper_local`

`paper_local` checks structural validity, resolvable references, assertion
contexts, evidence-link polarity, DOI and PMID resolution status, artifact
consistency with figure and table captions, and dataset consistency with
data-availability signals. Use it when the graph is close to author wording
and claims do not yet carry curated criticality or falsification criteria.

```bash
uv run csag validate paper_extraction.json \
  --profile paper_local \
  --report-out paper_extraction.validation.json
```

### `promoted_claim`

Use `promoted_claim` when a claim is ready for review or reuse outside the
source manuscript. It adds requirements for criticality, falsification
criteria, evidence strength, evidence-link rationales, decisive evidence, human
curation status, promotion review provenance, and text-span grounding.

```bash
uv run csag validate paper_extraction.json \
  --profile promoted_claim \
  --report-out paper_extraction.validation.json
```

### `benchmark_key`

Use `benchmark_key` for answer keys and scoring fixtures; `core,benchmark`
runs the same checks. It includes the `promoted_claim` checks and requires
every core or major assertion to have decisive evidence of at least moderate
strength unless the assertion is a limitation or speculation. [Benchmark
answer keys and scoring](benchmark-support.md) describes the scoring package.

```bash
uv run csag validate answer_key.hidden.json \
  --profile benchmark_key \
  --report-out answer_key.validation.json
```

## Failure severity

| Failure class | Severity | Why it matters |
|---------------|----------|----------------|
| Missing assertion context | Blocking | A CSAG claim is invalid without scope. |
| Dangling reference | Blocking | The graph cannot be traversed reliably. |
| Polarity outside `EvidenceLink` | Blocking | Support and refute semantics become ambiguous. |
| Missing text span on an assertion | Blocking for `lite`, promoted, and benchmark profiles | Claims cannot be audited against source text. |
| Weak evidence for a core benchmark claim | Blocking for `benchmark_key` | The answer key would reward unsupported claims. |
| Missing falsification criteria | Blocking for promoted and benchmark profiles | Core claims cannot be stress-tested. |
| Missing human curation status | Blocking for promoted and benchmark profiles | Reused claims show whether a curator verified or corrected them. |
| Missing promotion review provenance | Blocking for promoted and benchmark profiles | Reused claims record the review or curation activity that promoted them. |
| Missing optional enrichment | Warning or note | Acceptable when the source does not support the field. |
