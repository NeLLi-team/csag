---
name: csag-extraction
description: >-
  Extract a CSAG (Conditional Scientific Argumentation Graph) from a manuscript using the canonical
  argumentation spine (Assertions, EvidenceItems, EvidenceLinks, and optional InferenceSteps) while enforcing
  CSAG conditionality (no assertion without at least one Context). Also generates paper-grounded
  Q&A items using bundled QA templates.
license: LicenseRef-LBNL-NonCommercial
metadata:
  version: "1.0.0"
---

# csag-extraction

## Goal

Convert a manuscript into a CSAG (Conditional Scientific Argumentation Graph)
`PaperExtraction` instance, written as `paper_extraction.json`, that is valid
against the LinkML (Linked Data Modeling Language) schema in
`assets/csag.yaml`, grounded in text spans, canonical (support and refute
polarity only in evidence links, reasoning chains only in inference steps),
and conditional (every assertion carries at least one context).

`SKILL_DIR` is the directory that contains this `SKILL.md`; in the CSAG
repository it is `skills/csag-extraction`. Set it once, then run every script
as `uv run "$SKILL_DIR/scripts/<name>"`:

```bash
SKILL_DIR=skills/csag-extraction
```

The validator scripts import the `jsonschema` package. The CSAG project
declares it as a dependency, so `uv run` inside the repository provides it; a
copied skill directory needs `jsonschema` installed in the environment that
runs the scripts.

## Files in this skill

| Path | Content |
|------|---------|
| `assets/csag.yaml` | Authoritative LinkML schema. |
| `assets/csag.schema.json` | JSON Schema for `PaperExtraction`, generated from `csag.yaml`; the validator loads it. |
| `assets/csag.handoff.schema.json` | JSON Schema for `HandoffEnvelope`, generated from `csag.yaml`. |
| `assets/csag_qa_templates.yaml` | QA template catalog. |
| `references/CSAG_PLAYBOOK.md` | Class-by-class extraction guide with edge cases. |
| `scripts/validate_paper_extraction.py` | Profile validator; a failure blocks the extraction. |
| `scripts/csag_quality_report.py` | Quality report; `--strict` fails on issues. |
| `scripts/validate_handoff_envelope.py` | `HandoffEnvelope` validator, also reached through `csag validate --profile handoff`. |
| `scripts/csag_provenance.py` | Shared helper that hashes report inputs. |

## Invariants

- Every assertion has at least one context.
- Support and refute polarity are recorded only in evidence links.
- Contradiction, qualification, and replication between assertions are
  recorded only in assertion relations.
- Reasoning chains are recorded only in inference steps.
- Core and major objects are grounded with text spans.
- Every assertion carries a normalization status: `raw`,
  `partially_normalized`, or `fully_normalized`.

The validator rejects an assertion without contexts or without a normalization
status in every profile, and rejects `polarity`, `relation_type`, and
inference fields recorded on any other object type.

## Extraction scope

The extraction scope is the full manuscript: title, abstract, introduction,
methods, results, discussion, conclusion, and supplementary material when
available. When retrieval was driven by topic terms (organisms, genes,
methods), do not restrict assertions or evidence to sentences that mention
those terms.

## Procedure

### Phase 1: core graph (always)

1. Build the `PaperExtraction` metadata: `id`, `title`, and `doi` and `pmid`
   when available. Resolve `doi` and `pmid` from the source Markdown, the
   article JSON, TEI or XML, or local metadata whenever recoverable. When one
   or both stay unresolved, record `doi_status` and `pmid_status` entries with
   the value `resolved` or `unresolved` in
   `extraction_activities[].parameters`.
2. Extract artifacts when the manuscript exposes figure, table, or supplement
   captions.
3. Extract datasets when the manuscript exposes data-availability text,
   repository links, accessions, or project identifiers.
4. Extract entities, with ontology annotations when possible.
5. Extract assertions (hypotheses, result claims, conclusions). Each one has
   `contexts` (at least one) and `normalization_status`. Set `criticality`
   (`core`, `major`, `supporting`, `background`) when the importance of the
   claim can be judged, and `falsification_criteria` for every core or major
   assertion (the observation that would weaken or refute the claim).
6. Extract evidence items (results, analyses, citations).
7. Create evidence links from evidence item to assertion with `polarity`,
   `strength`, and `rationale`.
8. Add text spans that ground the core and major assertions, evidence items,
   and evidence links.

### Phase 2: study and experiment structure (when feasible)

- Add `Study` and `Experiment` objects.
- Enrich contexts (organism, cell type, tissue, disease) with entity
  references.

### Phase 3: conditions, reasoning, critiques, gaps, and QA (when present)

- Add `Condition` objects (dose, time, genotype, treatment regime).
- Add inference steps for explicit or implicit reasoning chains.
- Add `StudyCritique` and `KnowledgeGap` objects.
- Generate QA items from the templates.

## Coverage targets

For a full research article, unless the source is a short note or editorial
with little content, target:

- at least 1 assertion for the hypothesis, research question, or objective
  when present
- at least 2 result or conclusion assertions from different parts of the
  manuscript when present
- at least 2 evidence items and at least 2 evidence links when present
- at least 1 inference step when the `reasoning` profile is selected or when
  the manuscript combines several premises or pieces of evidence into a
  derived claim
- at least 1 critique or knowledge gap when the authors discuss one
- at least 1 artifact when the source has figure or table captions
- at least 1 dataset when the source has data-availability text, accessions,
  or repository links

When a category is absent from the manuscript, say so in `notes` for the
extraction or the assertion instead of omitting it silently.

Avoid these failure modes:

- an extraction with one assertion and one evidence item when richer claims
  are present
- extraction restricted to sentences that mention the retrieval topic terms
- mechanistic or statistical claims skipped because they sit outside the
  topic terms

## Model-assisted extraction

When a model assists the extraction, split the work in two steps:

1. Draft the scientific content: claims, evidence snippets, evidence polarity,
   inferences, critiques, gaps, artifacts, datasets, and exact source quotes.
2. Let tooling assemble the final `PaperExtraction`: deterministic IDs,
   reference fields, enum normalization, offset lookup from `exact_text`, and
   validator repair of mechanical schema-shape issues.

Do not rely on a model for all final bookkeeping in one pass. The common
failures are missing IDs, dangling references, scalar values where lists are
required, field aliases such as `evidence_id` instead of `evidence_item`,
wrong enum labels, and missing artifact or dataset metadata.

Use the validator as a feedback loop:

```bash
uv run "$SKILL_DIR/scripts/validate_paper_extraction.py" out/paper_extraction.json \
  --source-markdown out/paper.md \
  --article-json out/paper.article.json \
  --report-out out/paper_extraction.validation.json
```

For mechanical cleanup before curation, write a repaired candidate and inspect
`repair_actions` in the validation report:

```bash
uv run "$SKILL_DIR/scripts/validate_paper_extraction.py" out/paper_extraction.raw.json \
  --source-markdown out/paper.md \
  --article-json out/paper.article.json \
  --repair-out out/paper_extraction.repaired.json \
  --report-out out/paper_extraction.validation.json
```

Repairs normalize deterministic schema shape (field aliases, enum aliases,
scalar-to-list coercions, missing deterministic IDs, inferred artifact types)
and do not certify scientific correctness. The validation report also carries
machine-readable `structured_errors` and `error_summary`. With
`--repair-out`, the report's `inputs.extraction` record hashes the repaired
file and `inputs.source_extraction` keeps the original input.

## Identifier conventions

1. `PaperExtraction.id` is `pmid:<pmid>` when the PMID is known, else
   `doi:<doi>`, else `csag:doc/<slug>`.
2. Every local object ID has the form `csag:<type>/<document id>/<code>`, for
   example `csag:assertion/doi:10.1038/s41467-025-67401-4/A0001`. The
   per-class prefixes and codes are listed in `references/CSAG_PLAYBOOK.md`.
3. `TextSpan.document_id` is the same identifier as `PaperExtraction.id`.
4. When only a PMCID is available, use `pmc:<id>` and note in `notes` that
   PMID resolution is pending.
5. One `PaperExtraction` per source manuscript; never mix spans across
   manuscripts.
6. Record `extraction_activities` with `tool_name`, `tool_version`,
   `model_name` when a model was used, and `doi_status` and `pmid_status`
   parameters when those identifiers could not be resolved from the source.

## Validation and quality report

Run the validator and do not stop until it prints `OK`:

```bash
uv run "$SKILL_DIR/scripts/validate_paper_extraction.py" out/paper_extraction.json \
  --source-markdown out/paper.md \
  --article-json out/paper.article.json \
  --report-out out/paper_extraction.validation.json
```

Then run the quality report:

```bash
uv run "$SKILL_DIR/scripts/csag_quality_report.py" out/paper_extraction.json \
  --source-markdown out/paper.md \
  --article-json out/paper.article.json \
  --report-out out/paper_extraction.quality.json \
  --strict
```

Inspect `completeness`, `missing_or_weak`, `field_quality`, and `issues` in
the report. Resolve every entry in `issues` before you stop; fix each warning
in `missing_or_weak` or justify it in `notes`.

Before you finish, confirm:

- Assertions reflect the core claims of the study.
- Evidence links cover the core and major assertions, not only the first
  matched sentence.
- At least one text span anchors each non-trivial object.
- Absent components are stated (for example, no hypothesis section).
- `doi` and `pmid` are resolved when recoverable, or `doi_status` and
  `pmid_status` parameters are present in `extraction_activities`.
- `artifacts` are present when the source has figure or table captions.
- `datasets` are present when the source has data-availability text,
  accessions, or repository links.

## Profiles

Profiles are `lite`, `paper_local` (the validator default; `core` is an
alias), `promoted_claim`, and `benchmark_key`. Modules are `core`, `bio`,
`reasoning`, `research_state`, and `benchmark`; combine them with commas. Add
optional modules only when the artifact is meant to carry them:

- `--profile core,bio` for biological entity normalization, study and
  experiment structure, conditions, and assay variables.
- `--profile core,reasoning` for derived inference chains or claim-to-claim
  relations.
- `--profile core,benchmark` for answer-key and scoring artifacts.

Keep the reasoning layer separate from the core extraction. `InferenceStep`
and `AssertionRelation` often encode curator judgment or cross-manuscript
synthesis. A manuscript-local CSAG stays valid without those derived objects,
and derived objects are not author-stated evidence.

For higher-stakes use, validate with `--profile promoted_claim` (curated
claims) or `--profile benchmark_key` (scoring keys). These profiles also
require:

- an `ExtractionActivity` whose `activity_type` names human review or
  curation, and `curation_status` `human_verified` or `human_corrected` on
  every assertion and evidence link
- `criticality` and `falsification_criteria` on every assertion, and
  `strength` and `rationale` on every evidence link
- for every non-background assertion, a decisive evidence link (`supports`,
  `refutes`, or `mixed`) and text-span grounding on the assertion or on one of
  its linked evidence items
- with `benchmark_key`, at least moderate decisive evidence for every core
  and major assertion unless its `claim_role` is `limitation` or `speculation`

## Manuscript questions

Before you finish a `PaperExtraction`, answer these questions, internally or
as `qa_items`:

- What are the hypotheses, research questions, or objectives?
- What are the primary result claims, conclusions, or discoveries?
- What evidence supports each core and major assertion, and what evidence, if
  any, refutes it?
- Which assertions are core, major, supporting, or background?
- What observation or analysis would falsify or weaken each core or major
  assertion?
- What inference or mechanistic chains connect evidence to conclusions?
- What limitations or flaws are stated or strongly implied?
- What open knowledge gaps or future-work items are stated?

| Answer | Maps to |
|--------|---------|
| hypotheses, results, conclusions | `assertions` |
| claim importance | assertion `criticality` |
| falsifiability checks | assertion `falsification_criteria` |
| support or refute | `evidence_links` |
| reasoning chains | `inferences` |
| limitations | `critiques` |
| open questions | `knowledge_gaps` |
| question-driven outputs | `qa_items` (from `assets/csag_qa_templates.yaml`) |

## Normalization rubric

- `raw`: free text only; the triple fields may be empty.
- `partially_normalized`: some of subject, predicate, and object filled, or
  ambiguous mappings.
- `fully_normalized`: subject, predicate, and object present; subject and
  object reference entity IDs; the predicate is a CURIE (compact URI) or URI,
  preferably from the Relation Ontology (RO) or the Semanticscience
  Integrated Ontology (SIO).

## QA templates

Use `assets/csag_qa_templates.yaml` to instantiate `QAItem` and `Answer`
objects. Every answer cites `supporting_assertions`,
`supporting_evidence_links`, or both.

For edge cases and scoring guidance, see `references/CSAG_PLAYBOOK.md`.
