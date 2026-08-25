# Schema table

Field names are LinkML (Linked Data Modeling Language) slot identifiers from
`skills/csag-extraction/assets/csag.yaml`. Required fields are marked with `*`.
Provenance and curation slots reach the extracted record classes through the
`Record` and `ExtractedItem` mixins.

The schema has five modules. `core` is the minimum manuscript-local claim and
evidence ledger. `bio`, `reasoning`, `research_state`, and `benchmark` are
optional enrichment layers that reference core identifiers. [Validation
profiles](profiles.md) maps the modules to `--profile` values and explains why
the reasoning module is separate from `core`.

| Module | Object groups |
|--------|---------------|
| `core` | `PaperExtraction`, `TextSpan`, `Assertion`, `Context`, `EvidenceItem`, `EvidenceLink`, `StudyCritique`, `KnowledgeGap`, `Artifact`, `Dataset`, provenance and curation fields |
| `bio` | `Entity`, `EntityMention`, `OntologyAnnotation`, `Condition`, `Qualifier`, `Study`, `Experiment`, `Variable`, normalized assertion fields |
| `reasoning` | `InferenceStep`, `AssertionRelation` |
| `research_state` | `ResearchStateRecord`, `NextAction`, `Execution` |
| `benchmark` | `QAItem`, `Answer`, benchmark scoring metadata |

| Object class | Key fields | What it records |
|--------------|------------|-----------------|
| `PaperExtraction` | `id*`, `title*`, `schema_version*`, `validator_version*`, `doi`, `pmid`, `journal`, `publication_date`, `authors`, `keywords`, `mesh_terms`, `full_text_url`, `license`, `assertions*`, `evidence_items*`, `evidence_links*` | Bibliographic anchor and root container for one manuscript. |
| `TextSpan` | `document_id*`, `section_type*`, `start_char*`, `end_char*`, `exact_text`, `page_number`, `artifact_ref` | Character-level source grounding for extracted objects. |
| `Entity` with `EntityMention`, `OntologyAnnotation` | `entity_category`, `ontology_annotations`, `xrefs`, `mentions`, `term_id`, `term_label` | Normalized scientific term with cross-references and ontology mappings. |
| `Context` | `context_facet`, `organism`, `cell_type`, `tissue`, `disease_state`, `strain`, `developmental_stage`, `sex`, `age`, `environment_description`, `additional_context_qualifiers` | Biological or experimental scope. Every `Assertion` has at least one. |
| `Condition` | `parameter_type`, `value_text`, `value_number`, `value_unit`, `entity_involved`, `logical_expression` | Dose, time, genotype, treatment, or other claim parameter. |
| `Study` / `Experiment` / `Variable` | `study_type`, `study_contexts`, `experiments`, `sample_size`, `assay_type`, `variables`, `variable_role`, `variable_entity`, `measurement_type` | Study design, experiments, and measured or manipulated variables. |
| `Assertion` | `assertion_text*`, `claim_role*`, `assertion_type`, `normalization_status*`, `subject`, `predicate`, `object`, `contexts*` (at least one), `conditions`, `qualifiers`, `criticality`, `falsification_criteria` | Scoped claim or hypothesis, optionally normalized as a subject-predicate-object triple. |
| `EvidenceItem` | `evidence_type*`, `evidence_text`, `contexts`, `conditions`, `associated_experiment`, `associated_artifacts`, `results`, `referenced_works` | Structured evidence unit. Polarity is stored on `EvidenceLink`. |
| `Result` | `result_text`, `outcome`, `comparator`, `effect_size`, `effect_size_type`, `p_value`, `ci_low`, `ci_high`, `statistic`, `n` | Numerical result attached to evidence, such as an effect size, statistic, interval, or sample size. |
| `EvidenceLink` | `evidence_item*`, `assertion*`, `polarity*`, `strength`, `rationale` | Support, refute, mixed, or inconclusive edge from evidence to assertion. |
| `InferenceStep` | `input_assertions`, `input_evidence_links`, `output_assertion*`, `inference_method*`, `assumptions`, `inference_rationale` | Reasoning step that combines premises and evidence into a derived assertion. |
| `AssertionRelation` | `from_assertion*`, `to_assertion*`, `relation_type*`, `relation_rationale`, `related_work` | Typed claim-to-claim relation within or across manuscripts, including competing or alternative hypotheses. |
| `StudyCritique` | `critique_type`, `risk_domain`, `severity`, `impacted_assertions`, `impacted_evidence_items`, `mitigation_suggestions` | Threat to validity or risk-of-bias note tied to assertions or evidence. |
| `KnowledgeGap` | `gap_type`, `severity`, `related_assertions`, `suggested_actions` | Open question, missing test, replication need, contradiction, or generalizability gap. |
| `ResearchStateRecord` | `target_assertions`, `state*`, `current_read`, `rationale`, `recommended_next_actions` | Interpretation of a claim or branch after weighing the evidence. |
| `NextAction` | `action_type*`, `description*`, `target_assertions`, `target_knowledge_gaps`, `priority`, `due_date` | Next experiment, analysis, review, decision, branch, or merge step. |
| `Execution` | `execution_type*`, `execution_status*`, `command`, `started_on`, `completed_on`, `output_artifacts`, `generated_evidence_items`, `tested_assertions` | Run that generated evidence, tested claims, or produced durable artifacts. |
| `Artifact` / `Dataset` | `artifact_type`, `artifact_label`, `caption`, `accession`, `repository`, `dataset_url`, `dataset_license` | Figure, table, code, supplement, equation, or data deposit referenced by evidence. |
| `QAItem` / `Answer` | `question_text*`, `expected_answer_type*`, `answers`, `answer_type*`, `answer_text`, `answer_number`, `answer_boolean`, `answer_entity`, `supporting_assertions`, `supporting_evidence_links`, `answer_confidence` | Evidence-backed benchmark or downstream question-answer surface. |
| Provenance and curation mixins | `id*`, `label`, `description`, `aliases`, `notes`, `origin`, `curation_status`, `confidence_score`, `text_spans`, `created_on`, `created_by`, `generated_by`, `derived_from`, `ExtractionActivity` (`activity_type`, `tool_name`, `tool_version`, `model_name`, `model_version`, `run_id`, `run_datetime`, `parameters`) | Shared provenance and curation fields. Every mixed-in record has a stable ID; the other fields are optional. |
