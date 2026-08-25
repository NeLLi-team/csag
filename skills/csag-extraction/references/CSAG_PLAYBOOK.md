# CSAG playbook

This playbook is the class-by-class guide for extracting a CSAG (Conditional
Scientific Argumentation Graph) from a manuscript. It complements `SKILL.md`,
which holds the procedure, coverage targets, and validation commands. Every
statement here follows the LinkML (Linked Data Modeling Language) schema in
`assets/csag.yaml`; when the two disagree, the schema wins.

The task is information extraction and normalization, not summarization. The
deliverable is a valid `PaperExtraction` instance that is grounded in text
spans, canonical (support and refute polarity only in evidence links;
contradiction, qualification, and replication only in assertion relations;
reasoning chains only in inference steps), conditional (every assertion has at
least one context, and conditions when the manuscript states them), and made
of small atomic objects with stable IDs.

## Output contract

The deliverable is one JSON file, `paper_extraction.json`, that holds a single
`PaperExtraction` object. Its top-level keys are the slots of
`PaperExtraction`; the schema is closed and rejects any other key.

| Key | Content |
|-----|---------|
| `id`, `title`, `schema_version`, `validator_version` | Required. Document identifier, title, and the schema and validator versions. |
| `assertions`, `evidence_items`, `evidence_links` | Required, each with at least one object. |
| `abstract`, `doi`, `pmid`, `journal`, `publication_date`, `authors`, `keywords`, `mesh_terms`, `full_text_url`, `license` | Bibliographic metadata inherited from `Paper`. |
| `notes` | Curator notes, including statements of absent components. |
| `extraction_activities` | `ExtractionActivity` records for the runs that produced the extraction. |
| `artifacts`, `datasets`, `entities`, `studies` | Figures and tables, datasets, normalized entities, and study structure. |
| `inferences`, `assertion_relations` | Reasoning steps and typed assertion-to-assertion edges. |
| `critiques`, `knowledge_gaps`, `qa_items` | Limitations, open questions, and question-answer items. |
| `research_states`, `next_actions`, `executions` | Research-state records, recommended actions, and execution runs. |

Some classes never appear at the top level. Contexts are inline in
`Assertion.contexts`, `EvidenceItem.contexts`, and `Study.study_contexts`;
conditions in `Assertion.conditions` and `EvidenceItem.conditions`; results in
`EvidenceItem.results`; experiments in `Study.experiments`; variables in
`Experiment.variables`; and text spans in the `text_spans` list of the object
they ground (and in `EntityMention.mention_span`).

Every `id` is a URI or CURIE (compact URI). Use deterministic IDs so that a
repeated extraction of the same manuscript yields mostly the same IDs.

## ID conventions

The document ID is `pmid:<pmid>` when the PMID is known, else `doi:<doi>` (for
example `doi:10.1038/s41586-020-2216-3`), else `csag:doc/<slug>`, where
`<slug>` is the lowercased title with every run of characters other than
`a-z` and `0-9` replaced by an underscore, cut to 80 characters.

Every local object ID has the form `csag:<type>/<document id>/<code>` and is
unique within the extraction. The document ID appears in full
(`csag:assertion/doi:10.1038/s41467-025-67401-4/A0001`) or in its compact form
with colons removed and slashes replaced by underscores
(`csag:assertion/pmid35150280/A0001`); the lint report flags local IDs that
omit it. Context IDs start with `csag:context/`; the `lite` profile and the
quality report recognize contexts by that prefix.

| Class | ID pattern |
|-------|------------|
| `Assertion` | `csag:assertion/<docid>/A0001` |
| `EvidenceItem` | `csag:evidence/<docid>/E0001` |
| `EvidenceLink` | `csag:elink/<docid>/L0001` |
| `Context` | `csag:context/<docid>/C0001` |
| `Condition` | `csag:condition/<docid>/K0001` |
| `TextSpan` | `csag:span/<docid>/S0001` |
| `Entity` | `csag:entity/<docid>/EN0001` |
| `Artifact` | `csag:artifact/<docid>/F0001` |
| `Dataset` | `csag:dataset/<docid>/D0001` |
| `Study` | `csag:study/<docid>/S0001` |
| `Experiment` | `csag:experiment/<docid>/X0001` |
| `InferenceStep` | `csag:inference/<docid>/I0001` |
| `AssertionRelation` | `csag:arel/<docid>/RL0001` |
| `StudyCritique` | `csag:critique/<docid>/R0001` |
| `KnowledgeGap` | `csag:gap/<docid>/G0001` |
| `QAItem` | `csag:qa/<docid>/Q0001` |
| `Answer` | `csag:answer/<docid>/ANS0001` |
| `ExtractionActivity` | `csag:activity/<docid>/ACT0001` |

## Text spans

Ground every assertion, evidence item, critique, and knowledge gap with at
least one `TextSpan` when the text exists in the input, and ground evidence
link rationales when possible. A `TextSpan` requires `id`, `document_id` (the
document ID), `section_type` (a `SectionType` value: `title`, `abstract`,
`introduction`, `methods`, `results`, `discussion`, `conclusion`,
`supplementary`, `figure_caption`, `table_caption`, `other`), `start_char`,
and `end_char` (0-based, end exclusive). Add `exact_text`; `section_heading`,
`page_number`, and `artifact_ref` are optional.

When offsets are missing, compute them: search the section text for
`exact_text` and record the matching span. With several matches, choose the
one that matches the nearby phrasing. When there is no match (a paraphrase),
anchor a shorter verbatim substring instead. Never record invented offsets.

## Entities

Create an `Entity` for each biologically meaningful concept that assertions,
contexts, or conditions need: genes, proteins, variants, chemicals and drugs,
diseases, phenotypes, cell types, tissues and anatomy, organisms, assays and
methods. Set `entity_category` from `EntityCategory`; `xrefs` and `mentions`
(`EntityMention` objects with `entity_ref` and `mention_span`) are optional.
Only `id` is required.

When a confident mapping exists, add an `OntologyAnnotation` under
`ontology_annotations` with its own `id`, `term_id` as a CURIE (for example
`NCBITaxon:10090`, `CL:0000540`, `MONDO:0004979`, `CHEBI:15365`),
`match_type` (`exact`, `broad`, `narrow`, or `related`), and
`confidence_score`. When the mapping is uncertain, keep the entity without a
term and lower its confidence.

## Contexts and conditions

Every assertion has `contexts` with at least one `Context`; a `Context`
requires only `id`. Create one baseline context per manuscript, even if
coarse:

- `id`: `csag:context/<docid>/C0001`
- `context_facet`: `unspecified`
- `label`: "in this study"
- `origin`: `extractor_inferred`
- `confidence_score`: 0.5 to 0.7

Attach the baseline context to every assertion that has no more specific
context. In phase 2, add or enrich contexts with `organism` (NCBITaxon
preferred), `cell_type` (CL preferred), `tissue` (UBERON preferred),
`disease_state` (MONDO preferred), and `strain`, each as an entity ID; with
`developmental_stage`, `sex`, `age`, and `environment_description` as text;
and with `additional_context_qualifiers` (`Qualifier` objects with
`predicate` and a `value_text`, `value_number`, `value_unit`, or
`value_entity_ref`).

A `Condition` is a parameter that scopes a result or claim (dose, timepoint,
genotype, knockout or knockdown, temperature, stress). Create one in phase 3
when the manuscript defines the parameter and the parameter scopes a claim.
Its slots are `parameter_type` (an ontology term; OBI, EFO, or NCIT
recommended), `value_text`, `value_number`, `value_unit` (UCUM recommended),
`entity_involved` (an entity ID, for example the drug in a treatment), and
`logical_expression` for complex conditions; only `id` is required. Attach
conditions to `Assertion.conditions` and `EvidenceItem.conditions`. When a
parameter is contextual rather than conditional, record it as a context
qualifier instead.

## Assertions

An `Assertion` is one atomic scientific statement: a hypothesis, result claim,
conclusion or discovery, or a limitation or future-work statement (the last
two are often better recorded as a critique or knowledge gap). Extract several
small assertions instead of one long one.

Required slots: `id`, `assertion_text` (close to the author wording),
`claim_role` (a `ClaimRole` value: `background`, `hypothesis`,
`research_question`, `objective`, `method_claim`, `result_claim`,
`conclusion`, `discovery`, `speculation`, `limitation`, `future_work`),
`normalization_status`, and `contexts`. Optional slots: `assertion_type`
(`causal`, `associative`, `mechanistic`, `comparative`, `localization`,
`functional`, `descriptive`, `methodological`, `other`), `criticality`,
`falsification_criteria` (a list of strings), `conditions`, `qualifiers`,
`asserted_in_study` (a `Study` ID), `subject`, `predicate`, `object`, and the
common `origin`, `confidence_score`, and `text_spans`.

Set `normalization_status` to one of:

- `raw`: `assertion_text`, role and type, contexts, and spans; no triple.
- `partially_normalized`: some structured fields (for example subject and
  object entities), but the predicate is missing, ambiguous, or mapped only to
  a local `csag:` predicate.
- `fully_normalized`: `subject`, `predicate`, and `object` are present;
  subject and object reference entity IDs, not raw strings; the predicate is
  an ontology predicate where one exists (Relation Ontology (RO) or
  Semanticscience Integrated Ontology (SIO) preferred, a local `csag:`
  predicate otherwise); and qualifiers, contexts, and conditions are attached.

Fill the triple (`subject` entity ID, `predicate` CURIE, `object` entity ID)
when the statement is about a relationship. Do not force a triple onto a
narrative assertion ("this suggests that") unless it can be represented
cleanly.

## Evidence

An `EvidenceItem` is one unit of evidence: one experiment result summary
(often one figure or table panel), one statistical test summary, or one
literature citation used as evidence. Required slots: `id` and
`evidence_type` (an `EvidenceType` value: `experimental_result`,
`statistical_analysis`, `computational_model`, `observational_data`,
`literature_citation`, `meta_analysis`, `replication`, `control_result`,
`negative_result`, `expert_opinion`, `other`). Optional slots:
`evidence_text`, `contexts`, `conditions`, `associated_experiment` (an
`Experiment` ID), `associated_artifacts` (artifact IDs), `results` (inline
`Result` objects for numeric findings, with `result_text`, `outcome`,
`comparator`, `effect_size`, `effect_size_type`, `p_value`, `ci_low`,
`ci_high`, `statistic`, and `n`), and `referenced_works` (inline `Reference`
objects with `citation_text`, `doi`, `pmid`, `url`, and `year`).

An `EvidenceLink` is the only edge that carries support or refutation.
Required slots: `id`, `evidence_item`, `assertion`, and `polarity`
(`supports`, `refutes`, `mixed`, `inconclusive`). Add `strength`
(`very_strong`, `strong`, `moderate`, `weak`, `very_weak`, `unknown`) and a
short `rationale` that ties the evidence to the claim; the `promoted_claim`
and `benchmark_key` profiles require both. Link every assertion to the
evidence items that bear on it.

Strength heuristics:

- `very_strong`: strong design, clear effect, strong statistics, appropriate
  controls and replication
- `strong`: solid statistics and design, limited replication or sample size
- `moderate`: some evidence with caveats (small n, indirect measurement)
- `weak`: suggestive only, unclear statistics, qualitative
- `very_weak`: speculative or poorly supported
- `unknown`: cannot judge

Reflect uncertainty in `confidence_score`.

## Artifacts and datasets

An `Artifact` is a figure, table, or supplement the manuscript refers to.
Slots: `artifact_type` (`figure`, `table`, `supplementary`, `equation`,
`protocol`, `code`, `other`), `artifact_label` (for example "Figure 2" or
"Table S1"), and `caption`. A `Dataset` is a dataset the manuscript produced
or used. Slots: `accession`, `repository` (for example GEO, SRA, PRIDE,
Zenodo), `dataset_url`, and `dataset_license`. Only `id` is required for
either class.

## Studies and experiments

A `Study` groups the experiments of the manuscript. Slots: `study_type` (an
ontology term; OBI or EFO recommended), `study_contexts` (inline `Context`
objects), `experiments` (inline `Experiment` objects), and `sample_size`. An
`Experiment` has `assay_type` (OBI recommended) and `variables` (inline
`Variable` objects with `variable_role`: independent, dependent, control, or
confounder; `variable_entity`; `measurement_type`; and `value_text`,
`value_number`, `value_unit`). Only `id` is required for each class. Link an
assertion to its study through `asserted_in_study` and an evidence item to
its experiment through `associated_experiment`.

## Inference steps

Create an `InferenceStep` when the manuscript performs an explicit reasoning
jump: evidence for an intermediate claim leads to a mechanistic conclusion,
several premises yield a derived conclusion, or an observational association
plus an assumption yields a causal inference. Required slots: `id`,
`output_assertion`, and `inference_method` (an `InferenceMethod` value:
`statistical_inference`, `mechanistic_reasoning`, `causal_inference`,
`qualitative_interpretation`, `computational_inference`,
`analogy_or_prior_knowledge`, `other`). Give `input_evidence_links`
(preferred), `input_assertions`, or both; `assumptions` (assertion IDs) and a
short `inference_rationale` are optional. Do not build long chains the
manuscript does not support.

## Assertion relations

Create an `AssertionRelation` when the authors state a conflict with prior
literature, qualify or limit a claim, replicate or fail to replicate a prior
claim, or when two claims in the same manuscript contradict or qualify each
other. Required slots: `id`, `from_assertion`, `to_assertion`, and
`relation_type` (an `AssertionRelationType` value: `same_as`, `contradicts`,
`qualifies`, `competes_with`, `alternative_to`, `merged_into`, `generalizes`,
`specializes`, `derived_from`, `replicates`, `other`). `supports` and
`refutes` are not relation types; evidence links carry polarity. Add
`relation_rationale`, `related_work` (an external work identifier), and text
spans when present.

## Critiques and knowledge gaps

A `StudyCritique` records an explicit limitation or bias risk. Author-stated
limitations get `origin: author_stated`; inferred ones (for example,
uncorrected multiple testing) get `origin: extractor_inferred` and lower
confidence. Slots: `critique_type` (a `ThreatToValidityType` value:
`internal_validity`, `external_validity`, `construct_validity`,
`statistical_conclusion_validity`), `risk_domain` (a `RiskOfBiasDomain`
value), `severity` (`high`, `moderate`, `low`, `unknown`),
`impacted_assertions`, `impacted_evidence_items`, and
`mitigation_suggestions`; only `id` is required.

A `KnowledgeGap` records an open question or missing evidence. Author-stated
future work gets `origin: author_stated`; an inferred "replication needed"
gets `origin: extractor_inferred`. Slots: `gap_type` (a `GapType` value:
`missing_mechanism`, `missing_experiment`, `missing_control`,
`replication_needed`, `generalizability`, `data_missing`,
`inconsistent_results`, `unresolved_contradiction`, `other`), `severity`,
`related_assertions`, and `suggested_actions` (text, when the manuscript
suggests experiments); only `id` is required.

## Provenance and origin

Every extracted object can carry `origin` (`author_stated`, `author_implied`,
`extractor_inferred`, `curator_added`), `curation_status` (`unreviewed`,
`machine_extracted`, `human_verified`, `human_corrected`, `deprecated`),
`confidence_score` (0 to 1), and `notes`. Do not fabricate: when the
manuscript does not say it, do not record it; when you infer it, set
`origin: extractor_inferred` and lower the confidence.

## Extraction procedure

Inputs: manuscript metadata (DOI, PMID, title, journal, date) when available,
the manuscript text segmented by section (preferred), and figure and table
text when available. Output: one `paper_extraction.json`.

1. Initialize the extraction: set `id` (see "ID conventions"), `title`,
   `schema_version`, `validator_version`, the metadata fields that are
   present, and an `ExtractionActivity` in `extraction_activities` (see the
   identifier conventions in `SKILL.md`).
2. Create the baseline context `C0001` (label "in this study", facet
   `unspecified`).
3. Extract entities for every biological item that claims, evidence, or
   contexts need; add ontology annotations when confident.
4. Extract assertions: identify hypotheses, main findings, conclusions, and
   key negative results; split them into atomic assertions; attach at least
   one context; set `claim_role`, `assertion_type`, and
   `normalization_status`; add text spans.
5. Extract evidence items from figures, tables, and results text; add `Result`
   objects when numbers or statistics appear; attach contexts and conditions
   when available; add text spans.
6. Create evidence links: for each assertion, link the evidence items that
   bear on it and set polarity, strength, and rationale.
7. Phase 2, when possible: create `Study` and `Experiment` objects; link
   assertions through `asserted_in_study` and evidence items through
   `associated_experiment`; enrich contexts with organism, cell type, tissue,
   and disease.
8. Phase 3, when possible: extract conditions (dose, time, genotype,
   perturbation); add inference steps for explicit reasoning chains; add
   critiques and knowledge gaps; generate QA items from the templates.
9. Self-check: every assertion has at least one context; polarity appears
   only in evidence links; contradictions appear only in assertion relations;
   IDs are unique and every reference resolves; every text span has
   `start_char` less than `end_char`.

## QA generation

QA items let downstream systems query, validate, and reuse the graph. A `QAItem`
requires `id`, `question_text`, and `expected_answer_type` (a `QAAnswerType`
value: `boolean`, `numeric`, `categorical`, `entity`, `relation`,
`free_text`, `list`, `dataset_pointer`); give it `answers` with at least one
`Answer` and set `query_assertion` to the assertion the question is about. An
`Answer` requires `id` and `answer_type`; give it one of `answer_text`,
`answer_boolean`, `answer_number`, or `answer_entity`, plus
`supporting_assertions`, `supporting_evidence_links`, or both, and
`answer_confidence`. Prefer one answer per item; when the evidence is mixed,
use the categorical value `mixed`.

Compute the evidence status of an assertion from its evidence links. Weight
each link by strength: `very_strong` 3, `strong` 2, `moderate` 1, `weak` 0.5,
`very_weak` 0.25, `unknown` 0. Sum the weights of the `supports` links into a
support score and the weights of the `refutes` links into a refute score. The
status is `inconclusive` when both scores are 0; `supports` when the support
score is at least 1 and at least 1.5 times the refute score; `refutes` when
the refute score is at least 1 and at least 1.5 times the support score;
otherwise `mixed`.

The table lists the templates in `assets/csag_qa_templates.yaml`. Create
`CSAG_QA_01_STATUS` for every assertion that has an evidence link, and
`CSAG_QA_04_BOOL` only when the status is `supports` or `refutes`. Create the
triple templates (05 and 06) only for `fully_normalized` assertions with at
least one meaningful context. Several items per assertion are fine.

| Template | Phase | Question | Answer | Use when |
|----------|-------|----------|--------|----------|
| `CSAG_QA_01_STATUS` | 1 | What is the evidence status for the claim: "{assertion_text}"? | categorical: `supports`, `refutes`, `mixed`, `inconclusive`; cite the evidence links | the assertion has at least one evidence link |
| `CSAG_QA_02_EVIDENCE_SUPPORT` | 1 | What evidence supports the claim: "{assertion_text}"? | list of supporting evidence items or links | at least one `supports` link exists |
| `CSAG_QA_03_EVIDENCE_REFUTE` | 1 | What evidence refutes the claim: "{assertion_text}"? | list of refuting evidence items or links | at least one `refutes` link exists |
| `CSAG_QA_04_BOOL` | 1 | Based on this paper, is it supported that: "{assertion_text}"? | boolean: true for `supports`, false for `refutes` | the status is `supports` or `refutes` |
| `CSAG_QA_05_TRIPLE_BOOL` | 3 | In {context_label}, does {subject_label} ({subject_id}) {predicate_label_or_id} {object_label} ({object_id})? | boolean derived from the evidence status | fully normalized and the status is `supports` or `refutes` |
| `CSAG_QA_06_TRIPLE_STATUS` | 3 | In {context_label}, what is the evidence status that {subject_label} {predicate_label_or_id} {object_label}? | categorical: `supports`, `refutes`, `mixed`, `inconclusive` | fully normalized with at least one evidence link |
| `CSAG_QA_07_CONTEXT_LIST` | 2 | Under what biological contexts is the claim "{assertion_text}" evaluated in this paper? | list of context IDs or labels | always possible; most useful with several contexts |
| `CSAG_QA_08_CONDITION_LIST` | 3 | Under what conditions (dose/time/genotype/treatment) does the claim "{assertion_text}" hold? | list of condition IDs or summaries | the assertion has at least one condition |
| `CSAG_QA_09_MECHANISM` | 3 | What mechanism is proposed to explain: "{assertion_text}"? | short free text that cites inference steps and evidence links | an inference step produces a mechanistic assertion |
| `CSAG_QA_10_LIMITATIONS` | 3 | What limitations or flaws could weaken the claim: "{assertion_text}"? | list of critique IDs or short text | a critique impacts the assertion |
| `CSAG_QA_11_GAPS` | 3 | What knowledge gaps remain for the claim: "{assertion_text}"? | list of knowledge gap IDs or short text | a knowledge gap relates to the assertion |
| `CSAG_QA_12_CONFLICTS` | 3 | Are there conflicting statements in this paper or cited literature about: "{assertion_text}"? | categorical: `yes`, `no`, `unclear` | an assertion relation of type `contradicts` or `qualifies` involves the assertion |

## Quality bar

- Assertions are atomic and cover the contributions of the manuscript.
- Evidence links let a reader retrieve the supporting and refuting evidence
  for each assertion.
- Every assertion has a context, coarse if necessary and enriched when
  possible.
- `fully_normalized` is set only when the triple is solid.
- QA items answer what is supported, where, under what conditions, and by
  what evidence.
