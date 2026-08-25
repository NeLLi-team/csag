# CSAG schema reference

Authoritative source: `skills/csag-extraction/assets/csag.yaml`.

## Controlled vocabularies

### ArtifactType

Artifact kinds referenced in a paper.

Values: `code`, `equation`, `figure`, `other`, `protocol`, `supplementary`, `table`

### AssertionCriticality

Benchmark/evaluation importance of an assertion.

Values: `background`, `core`, `major`, `supporting`

### AssertionRelationType

Relationships between assertions (within or across papers).

Values: `alternative_to`, `competes_with`, `contradicts`, `derived_from`, `generalizes`, `merged_into`, `other`, `qualifies`, `replicates`, `same_as`, `specializes`

### AssertionType

Semantic type of an assertion.

Values: `associative`, `causal`, `comparative`, `descriptive`, `functional`, `localization`, `mechanistic`, `methodological`, `other`

### ClaimRole

The rhetorical/functional role an assertion plays in the paper.

Values: `background`, `conclusion`, `discovery`, `future_work`, `hypothesis`, `limitation`, `method_claim`, `objective`, `research_question`, `result_claim`, `speculation`

### ContextFacet

Optional coarse facet label for a Context (useful for phase 1/2).

Values: `cell_type`, `dataset`, `disease_state`, `environment`, `evolutionary_context`, `model_system`, `organism`, `other`, `tissue`, `unspecified`

### CurationStatus

Review state for an extracted object.

Values: `deprecated`, `human_corrected`, `human_verified`, `machine_extracted`, `unreviewed`

### EntityCategory

High-level categories for normalized entities.

Values: `anatomical_structure`, `assay`, `biological_process`, `cell_type`, `cellular_component`, `chemical`, `dataset`, `disease`, `drug`, `environment`, `gene`, `metabolite`, `method`, `molecular_function`, `organism`, `other`, `pathway`, `phenotype`, `protein`, `strain`, `tissue`, `transcript`, `variant`

### EvidenceType

The kind of evidence item extracted from the paper.

Values: `computational_model`, `control_result`, `experimental_result`, `expert_opinion`, `literature_citation`, `meta_analysis`, `negative_result`, `observational_data`, `other`, `replication`, `statistical_analysis`

### ExecutionStatus

Status of an execution/run that generated or tested evidence.

Values: `blocked`, `cancelled`, `completed`, `failed`, `planned`, `running`

### GapType

Types of knowledge gaps or future work items.

Values: `data_missing`, `generalizability`, `inconsistent_results`, `missing_control`, `missing_experiment`, `missing_mechanism`, `other`, `replication_needed`, `unresolved_contradiction`

### HandoffActionStatus

Lifecycle state of an action in an agent handoff.

Values: `blocked`, `cancelled`, `completed`, `in_progress`, `proposed`, `ready`

### HandoffArtifactRole

Role of a content-hashed artifact in a handoff.

Values: `article_metadata`, `code`, `dataset`, `other`, `paper_extraction`, `quality_report`, `result`, `source_markdown`, `validation_report`

### HandoffAssessmentStatus

Review status of an assessment recorded in a handoff.

Values: `accepted`, `disputed`, `open`, `superseded`

### HandoffConflictStatus

Resolution state of a conflict between handoff revisions.

Values: `open`, `resolved`

### InferenceMethod

Reasoning mode used to connect evidence/premises to a conclusion.

Values: `analogy_or_prior_knowledge`, `causal_inference`, `computational_inference`, `mechanistic_reasoning`, `other`, `qualitative_interpretation`, `statistical_inference`

### NextActionType

Type of next action recommended for a claim, gap, or branch.

Values: `analysis`, `branch`, `data_collection`, `decision`, `experiment`, `merge`, `other`, `replication`, `review`

### NormalizationStatus

Normalization status of an Assertion into a structured triple.

Values: `fully_normalized`, `partially_normalized`, `raw`

### Origin

Where an extracted object comes from.

Values: `author_implied`, `author_stated`, `curator_added`, `extractor_inferred`

### Polarity

Direction of an evidence link with respect to an assertion.

Values: `inconclusive`, `mixed`, `refutes`, `supports`

### QAAnswerType

Expected shape of an answer to a question.

Values: `boolean`, `categorical`, `dataset_pointer`, `entity`, `free_text`, `list`, `numeric`, `relation`

### ResearchState

Current review or investigation state for a claim or research branch.

Values: `blocked`, `merged`, `mixed`, `needs_evidence`, `needs_replication`, `open`, `rejected`, `supported`

### RiskOfBiasDomain

Common risk-of-bias or failure modes.

Values: `attrition_bias`, `batch_effect`, `confounding`, `contamination`, `data_leakage`, `data_quality`, `detection_bias`, `measurement_error`, `model_overfitting`, `multiple_testing`, `other`, `p_hacking`, `performance_bias`, `reporting_bias`, `selection_bias`

### SectionType

Canonical paper sections for anchoring extracted snippets.

Values: `abstract`, `conclusion`, `discussion`, `figure_caption`, `introduction`, `methods`, `other`, `results`, `supplementary`, `table_caption`, `title`

### SeverityLevel

Qualitative severity for critiques and knowledge gaps.

Values: `high`, `low`, `moderate`, `unknown`

### StrengthLevel

Qualitative evidence-strength label.

Values: `moderate`, `strong`, `unknown`, `very_strong`, `very_weak`, `weak`

### ThreatToValidityType

Broad threat-to-validity category.

Values: `construct_validity`, `external_validity`, `internal_validity`, `statistical_conclusion_validity`

## Classes

### Answer

A single answer to a QA item, linked to assertions/evidence.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `answer_type` | `QAAnswerType` | one, required | The type/shape of this answer. |
| `answer_text` | `string` | one | Free-text answer. |
| `answer_number` | `float` | one | Numeric answer. |
| `answer_boolean` | `boolean` | one | Boolean answer. |
| `answer_entity` | `uriorcurie` | one | Entity answer (Entity id). |
| `supporting_assertions` | `uriorcurie` | many | Assertions that justify the answer. |
| `supporting_evidence_links` | `uriorcurie` | many | Evidence links supporting the answer. |
| `answer_confidence` | `float` | one | Confidence in this answer. |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### Artifact

A figure/table/supplemental artifact referred to in the paper.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `artifact_type` | `ArtifactType` | one | Type of artifact (figure/table/etc). |
| `artifact_label` | `string` | one | Label such as "Figure 2" or "Table S1". |
| `caption` | `string` | one | Artifact caption. |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### Assertion

A hypothesis/claim/result/conclusion. Optionally normalized as a triple (subject, predicate, object). CSAG rule: every Assertion has at least one Context.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `assertion_text` | `string` | one, required | Natural-language form of the assertion, close to author wording. |
| `criticality` | `AssertionCriticality` | one | Evaluation importance of the assertion for ground-truth and scoring use. |
| `falsification_criteria` | `string` | many | Concrete observations or analyses that would weaken, refute, or require revising the assertion. |
| `claim_role` | `ClaimRole` | one, required | Rhetorical role of the assertion. |
| `assertion_type` | `AssertionType` | one | Semantic type, for example causal, mechanistic, or associative. |
| `normalization_status` | `NormalizationStatus` | one, required | Normalization status of the assertion triple (raw/partial/full). |
| `subject` | `uriorcurie` | one | Entity reference (Entity id) for subject of a normalized triple. |
| `predicate` | `uriorcurie` | one | Predicate/relation CURIE/URI (RO/SIO recommended). |
| `object` | `uriorcurie` | one | Entity reference (Entity id) for object of a normalized triple. |
| `contexts` | `Context` | many, required | Contexts under which an assertion/evidence holds. |
| `conditions` | `Condition` | many | Conditions/parameters required for an observation/claim. |
| `qualifiers` | `Qualifier` | many | Generic qualifiers that scope/condition the assertion (extra beyond Context/Condition). |
| `asserted_in_study` | `uriorcurie` | one | Reference to a Study (Study id) where the assertion is posed/tested/concluded. |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### AssertionRelation

A typed edge from one Assertion to another, for example contradicts, qualifies, or replicates. This is the canonical location for contradiction/qualification to avoid duplicated semantics.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `from_assertion` | `uriorcurie` | one, required | Source assertion for the relation edge. |
| `to_assertion` | `uriorcurie` | one, required | Target assertion for the relation edge. |
| `relation_type` | `AssertionRelationType` | one, required | Type of relation between assertions. |
| `relation_rationale` | `string` | one | Rationale for the assertion relation. |
| `related_work` | `uriorcurie` | one | Optional external work identifier if relating to an external claim. |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### Author

An author of a paper.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `id` | `uriorcurie` | one, required | ORCID URI is recommended when available. |
| `label` | `string` | one | Human-friendly short label. |
| `affiliation` | `string` | one | Author affiliation (free text). |

### Condition

Specific parameters/settings required for an observation/claim to hold (dose, timepoint, genotype, etc). Prefer ontology terms for parameter_type where possible; otherwise use a CSAG-local term.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `parameter_type` | `uriorcurie` | one | Ontology term or controlled CURIE describing the parameter (OBI/EFO/NCIT recommended). |
| `value_text` | `string` | one | Text value for a qualifier/condition/result. |
| `value_number` | `float` | one | Numeric value for a qualifier/condition/result. |
| `value_unit` | `string` | one | Unit (UCUM recommended). |
| `entity_involved` | `uriorcurie` | one | Entity reference implicated by the condition, for example a drug used in a treatment. |
| `logical_expression` | `string` | one | Logical expression for complex conditions, for example "A AND (B OR C)". |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### Context

The broader biological or experimental context in which an assertion/evidence is stated. In phase 1, Context may be coarse, for example facet=unspecified with label="in this study". In phase 2, populate organism/cell_type/tissue/disease_state/etc with Entity references.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `context_facet` | `ContextFacet` | one | Coarse context facet (helps early extraction). |
| `organism` | `uriorcurie` | one | Entity reference (Entity id) for organism (NCBITaxon recommended). |
| `cell_type` | `uriorcurie` | one | Entity reference for cell type (CL recommended). |
| `tissue` | `uriorcurie` | one | Entity reference for tissue/anatomy (UBERON recommended). |
| `disease_state` | `uriorcurie` | one | Entity reference for disease context (MONDO recommended). |
| `strain` | `uriorcurie` | one | Entity reference for strain (NCBITaxon/other as available). |
| `developmental_stage` | `string` | one | Developmental stage (free text or ontology term CURIE as string). |
| `sex` | `string` | one | Sex (free text or ontology term CURIE as string). |
| `age` | `string` | one | Age description, for example "8-week" or "adult". |
| `environment_description` | `string` | one | Free text environment details not captured elsewhere. |
| `additional_context_qualifiers` | `Qualifier` | many | Additional context qualifiers (predicate/value pairs). |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### Corpus

A collection of CSAG-extracted papers.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `documents` | `PaperExtraction` | many | Per-paper extraction records. |
| `extraction_activities` | `ExtractionActivity` | many | Extraction runs/activities used to generate the corpus or paper extraction. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |

### Dataset

A dataset produced or used by the paper.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `accession` | `string` | one | Accession identifier, for example a GEO or SRA accession. |
| `repository` | `string` | one | Repository name, for example GEO, SRA, PRIDE, or Zenodo. |
| `dataset_url` | `uri` | one | URL to dataset. |
| `dataset_license` | `uri` | one | Dataset license. |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### Entity

A normalized entity such as a gene, chemical, disease, or cell type.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `entity_category` | `EntityCategory` | one | High-level category of the entity. |
| `ontology_annotations` | `OntologyAnnotation` | many | Ontology normalization records. |
| `xrefs` | `uriorcurie` | many | External database cross-references (CURIEs/URIs). |
| `mentions` | `EntityMention` | many | Mentions of the entity grounded to spans. |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### EntityMention

A mention of an entity in the paper, grounded to text.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `entity_ref` | `uriorcurie` | one | Reference to an Entity. |
| `mention_span` | `TextSpan` | one | Text span grounding an entity mention. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### EvidenceItem

An evidence unit (result/analysis/citation) that can link to one or more assertions. IMPORTANT: EvidenceItem itself does NOT encode support/refute; that is canonicalized in EvidenceLink.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `evidence_type` | `EvidenceType` | one, required | Category of evidence item. |
| `evidence_text` | `string` | one | Short description of the evidence item. |
| `contexts` | `Context` | many | Contexts under which an assertion/evidence holds. |
| `conditions` | `Condition` | many | Conditions/parameters required for an observation/claim. |
| `associated_experiment` | `uriorcurie` | one | Reference to an Experiment that produced this evidence. |
| `associated_artifacts` | `uriorcurie` | many | References to figures/tables supporting this evidence. |
| `results` | `Result` | many | Structured results reported in this evidence item. |
| `referenced_works` | `Reference` | many | External works cited as evidence. |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### EvidenceLink

Canonical edge EvidenceItem -> Assertion with support/refute polarity and strength. This is the only place where support/refutation is encoded (prevents inconsistency).

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `evidence_item` | `uriorcurie` | one, required | Reference to an EvidenceItem. |
| `assertion` | `uriorcurie` | one, required | Reference to an Assertion. |
| `polarity` | `Polarity` | one, required | Whether evidence supports/refutes the assertion. |
| `strength` | `StrengthLevel` | one | Strength label for the evidence link. |
| `rationale` | `string` | one | Explanation of why the evidence supports/refutes the assertion. |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### Execution

A run or execution that generated evidence, tested a claim, or produced inspectable artifacts.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `execution_type` | `string` | one, required | Kind of execution/run, such as benchmark, notebook, analysis script, simulation, or wet-lab assay. |
| `execution_status` | `ExecutionStatus` | one, required | Status of the execution/run. |
| `command` | `string` | one | Command, protocol step, or run descriptor used for the execution. |
| `started_on` | `datetime` | one | Execution start timestamp. |
| `completed_on` | `datetime` | one | Execution completion timestamp. |
| `output_artifacts` | `uriorcurie` | many | Artifact IDs produced by the execution/run. |
| `generated_evidence_items` | `uriorcurie` | many | EvidenceItem IDs generated or materially supported by the execution/run. |
| `tested_assertions` | `uriorcurie` | many | Assertion IDs tested by the execution/run. |
| `url` | `uri` | one | URL for the referenced work. |
| `parameters` | `KeyValue` | many | Key-value parameters. |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### Experiment

An experiment/assay within a study.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `assay_type` | `uriorcurie` | one | Ontology term for assay type (OBI recommended). |
| `variables` | `Variable` | many | Variables measured/manipulated in an experiment. |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### ExtractedItem

A record grounded to text spans.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### ExtractionActivity

A run of an extraction tool/pipeline component.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `activity_type` | `string` | one | Activity type, for example claim extraction, named-entity recognition, or human review. |
| `tool_name` | `string` | one | Extraction tool name. |
| `tool_version` | `string` | one | Extraction tool version. |
| `model_name` | `string` | one | Model name (if applicable). |
| `model_version` | `string` | one | Model version/checkpoint. |
| `agent_uri` | `uriorcurie` | one | URI/CURIE identifying the responsible actor (tool, service, or person). |
| `run_id` | `string` | one | Run identifier. |
| `run_datetime` | `datetime` | one | Extraction run datetime. |
| `parameters` | `KeyValue` | many | Key-value parameters. |

### HandoffAction

Owned unit of work with dependency and completion contracts.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `action_type` | `NextActionType` | one, required | Type of next action. |
| `description` | `string` | one, required | Longer free-text description. |
| `owner` | `uriorcurie` | one, required | Agent or person accountable for an action. |
| `action_status` | `HandoffActionStatus` | one, required | Lifecycle state of a handoff action. |
| `dependencies` | `uriorcurie` | many | HandoffAction IDs that must complete before this action is ready. |
| `acceptance_criteria` | `string` | many, required | Observable conditions that define action completion. |
| `target_assertions` | `uriorcurie` | many | Assertions this state, next action, or execution is about. |
| `target_knowledge_gaps` | `uriorcurie` | many | KnowledgeGap IDs this next action addresses. |
| `created_on` | `datetime` | one, required | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one, required | Actor responsible (tool URI or ORCID). |

### HandoffArtifactDigest

Content identity and location for an exchanged source, input, or output artifact.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `artifact_role` | `HandoffArtifactRole` | one, required | Role of an artifact in the handoff. |
| `artifact_path` | `string` | one, required | Bundle-relative path or non-file external locator for an artifact; absolute and escaping local paths are rejected. |
| `sha256` | `Sha256Digest` | one, required | SHA-256 digest of the artifact bytes. |
| `media_type` | `string` | one | IANA media type when known. |
| `byte_size` | `integer` | one | Artifact size in bytes when known. |

### HandoffAssessment

Agent assessment with inspectable evidence and execution bases.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `assessment_status` | `HandoffAssessmentStatus` | one, required | Review status of an assessment. |
| `assessment_text` | `string` | one, required | Concise assessment or decision-ready interpretation. |
| `target_assertions` | `uriorcurie` | many | Assertions this state, next action, or execution is about. |
| `basis_artifacts` | `uriorcurie` | many | HandoffArtifactDigest IDs used as assessment evidence. |
| `basis_refs` | `uriorcurie` | many | IDs inside source artifacts, such as assertions or evidence items, used as assessment evidence. |
| `basis_executions` | `uriorcurie` | many | HandoffExecution IDs used as assessment evidence. |
| `created_on` | `datetime` | one, required | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one, required | Actor responsible (tool URI or ORCID). |

### HandoffConflict

Explicit disagreement between revision heads and its resolution state.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `conflict_status` | `HandoffConflictStatus` | one, required | Whether a revision conflict remains open or has been resolved. |
| `description` | `string` | one, required | Longer free-text description. |
| `competing_heads` | `uriorcurie` | many, required | Revision heads whose changes conflict. |
| `resolution` | `string` | one | Recorded resolution for a resolved conflict. |
| `resolved_by_head` | `uriorcurie` | one | Current revision head that contains the conflict resolution. |
| `created_on` | `datetime` | one, required | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one, required | Actor responsible (tool URI or ORCID). |

### HandoffEnvelope

Versioned exchange record for agent work over one or more content-hashed PaperExtraction snapshots. Collaboration state belongs here rather than in the source-grounded PaperExtraction, and state changes should create new revisions.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `envelope_version` | `HandoffEnvelopeVersion` | one, required | Version of the HandoffEnvelope contract used by this artifact. |
| `revision` | `uriorcurie` | one, required | Stable identifier for a handoff revision; it is not a digest of the envelope bytes. |
| `parents` | `uriorcurie` | many | Immediate parent revision identifiers. |
| `source_artifacts` | `HandoffArtifactDigest` | many, required | Content-hashed source snapshots on which the handoff is based. |
| `assessments` | `HandoffAssessment` | many | Agent assessments and the artifacts, claims, or executions that support them. |
| `actions` | `HandoffAction` | many | Owned work items with dependencies and acceptance criteria. |
| `executions` | `HandoffExecution` | many | Runs/executions that generated evidence, tested assertions, or produced inspectable artifacts. |
| `conflicts` | `HandoffConflict` | many | Open or resolved conflicts between revision heads. |
| `current_heads` | `uriorcurie` | many, required | Revision identifiers that are current workspace heads. |
| `created_on` | `datetime` | one, required | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one, required | Actor responsible (tool URI or ORCID). |

### HandoffExecution

Run record tied to an action, with content-hashed inputs and outputs.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `action_ref` | `uriorcurie` | one, required | HandoffAction ID executed by a run. |
| `execution_type` | `string` | one, required | Kind of execution/run, such as benchmark, notebook, analysis script, simulation, or wet-lab assay. |
| `execution_status` | `ExecutionStatus` | one, required | Status of the execution/run. |
| `command` | `string` | one | Command, protocol step, or run descriptor used for the execution. |
| `inputs` | `HandoffArtifactDigest` | many, required | Content-hashed artifacts consumed by an execution. |
| `outputs` | `HandoffArtifactDigest` | many | Content-hashed artifacts produced by an execution. |
| `environment` | `EnvironmentLockReference` | one, required | Environment lockfile locator followed by its SHA-256 digest. |
| `code_commit` | `string` | one, required | Version-control commit that supplied the executed code, or an explicit uncommitted-tree descriptor for a development fixture. |
| `execution_outcome` | `string` | one | Observed execution result, including failure information when applicable. |
| `started_on` | `datetime` | one, required | Execution start timestamp. |
| `completed_on` | `datetime` | one | Execution completion timestamp. |
| `created_by` | `uriorcurie` | one, required | Actor responsible (tool URI or ORCID). |

### InferenceStep

A reasoning step chaining premises/evidence into a derived assertion. This captures evidence chains and mechanistic reasoning explicitly.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `input_assertions` | `uriorcurie` | many | Premise assertions used in an inference step. |
| `input_evidence_links` | `uriorcurie` | many | Evidence links used as inputs to the inference step. |
| `output_assertion` | `uriorcurie` | one, required | The conclusion assertion produced by the inference step. |
| `inference_method` | `InferenceMethod` | one, required | Reasoning mode. |
| `assumptions` | `uriorcurie` | many | Assumptions (assertions) needed for the inference. |
| `inference_rationale` | `string` | one | Free-text rationale for the inference step. |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### KeyValue

Key-value record.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `key` | `string` | one | Key for a parameter. |
| `value` | `string` | one | Value for a parameter. |

### KnowledgeGap

An open question or missing evidence item (author-stated or extractor-inferred).

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `gap_type` | `GapType` | one | Type of knowledge gap. |
| `severity` | `SeverityLevel` | one | Severity label. |
| `related_assertions` | `uriorcurie` | many | Assertions related to the knowledge gap. |
| `suggested_actions` | `string` | many | Suggested experiments/analyses to address the gap. |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### NextAction

A concrete next experiment, analysis, review, decision, branch, or merge action.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `action_type` | `NextActionType` | one, required | Type of next action. |
| `description` | `string` | one, required | Longer free-text description. |
| `target_assertions` | `uriorcurie` | many | Assertions this state, next action, or execution is about. |
| `target_knowledge_gaps` | `uriorcurie` | many | KnowledgeGap IDs this next action addresses. |
| `priority` | `StrengthLevel` | one | Relative priority or urgency of a next action. |
| `due_date` | `date` | one | Optional due date for a next action. |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### OntologyAnnotation

A mapping from extracted text to an ontology term.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `term_id` | `uriorcurie` | one | Ontology term CURIE/URI used for normalization. |
| `term_label` | `string` | one | Label of the ontology term at extraction time. |
| `match_type` | `string` | one | Match type (exact/broad/narrow/related). |
| `evidence_code` | `uriorcurie` | one | Optional ECO/SEPIO evidence code term. |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### Paper

Bibliographic metadata for a scientific paper.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `title` | `string` | one | Paper title. |
| `abstract` | `string` | one | Paper abstract. |
| `doi` | `string` | one | DOI string, for example 10.xxxx/xxxx. |
| `pmid` | `string` | one | PubMed ID string. |
| `journal` | `string` | one | Journal or venue. |
| `publication_date` | `date` | one | Publication date. |
| `authors` | `Author` | many | Author list. |
| `keywords` | `string` | many | Keywords. |
| `mesh_terms` | `string` | many | MeSH terms (if available). |
| `full_text_url` | `uri` | one | URL where the full text can be accessed. |
| `license` | `uri` | one | License URL. |
| `schema_version` | `string` | one | CSAG schema version used to create or validate this extraction. |
| `validator_version` | `string` | one | Validator version used for the latest validation report. |

### PaperExtraction

A paper plus extracted CSAG objects.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `extraction_activities` | `ExtractionActivity` | many | Extraction runs/activities used to generate the corpus or paper extraction. |
| `artifacts` | `Artifact` | many | Figures/tables/supplemental artifacts. |
| `datasets` | `Dataset` | many | Datasets/accessions. |
| `entities` | `Entity` | many | Normalized entities mentioned/implied in the paper. |
| `studies` | `Study` | many | Studies/experiments described in the paper. |
| `assertions` | `Assertion` | many, required | Hypotheses/claims/results/conclusions extracted from the paper. |
| `evidence_items` | `EvidenceItem` | many, required | Evidence units (results/analyses/citations). |
| `evidence_links` | `EvidenceLink` | many, required | Canonical EvidenceItem -> Assertion links with support/refute polarity. |
| `inferences` | `InferenceStep` | many | Evidence/premise chains producing derived assertions. |
| `assertion_relations` | `AssertionRelation` | many | Relations between assertions (contradicts/qualifies/replicates/etc). |
| `critiques` | `StudyCritique` | many | Study limitations/flaws and risk-of-bias. |
| `knowledge_gaps` | `KnowledgeGap` | many | Open questions/missing evidence/future work. |
| `qa_items` | `QAItem` | many | Question/answer items linked to extracted claims and evidence. |
| `research_states` | `ResearchStateRecord` | many | Current interpretation/state records for assertions or competing research branches. |
| `next_actions` | `NextAction` | many | Next experiments, analyses, reviews, decisions, or branch operations recommended by the extraction or curator. |
| `executions` | `Execution` | many | Runs/executions that generated evidence, tested assertions, or produced inspectable artifacts. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `title` | `string` | one, required | Paper title. |
| `abstract` | `string` | one | Paper abstract. |
| `doi` | `string` | one | DOI string, for example 10.xxxx/xxxx. |
| `pmid` | `string` | one | PubMed ID string. |
| `journal` | `string` | one | Journal or venue. |
| `publication_date` | `date` | one | Publication date. |
| `authors` | `Author` | many | Author list. |
| `keywords` | `string` | many | Keywords. |
| `mesh_terms` | `string` | many | MeSH terms (if available). |
| `full_text_url` | `uri` | one | URL where the full text can be accessed. |
| `license` | `uri` | one | License URL. |
| `schema_version` | `string` | one, required | CSAG schema version used to create or validate this extraction. |
| `validator_version` | `string` | one, required | Validator version used for the latest validation report. |

### ProvenanceRecord

Minimal provenance record compatible with PROV-O/PAV patterns.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### QAItem

A question with answers grounded in extracted assertions and evidence.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `question_text` | `string` | one, required | Natural-language question. |
| `query_assertion` | `uriorcurie` | one | Optional reference to an Assertion representing the question in structured form. |
| `normalized_query` | `string` | one | Optional normalized form of the question (templated/structured). |
| `expected_answer_type` | `QAAnswerType` | one, required | Expected answer type. |
| `answers` | `Answer` | many | Candidate answers with evidence. |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### Qualifier

A flexible predicate/value qualifier for scoping assertions or contexts.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `predicate` | `uriorcurie` | one | Predicate/relation CURIE/URI (RO/SIO recommended). |
| `value_text` | `string` | one | Text value for a qualifier/condition/result. |
| `value_number` | `float` | one | Numeric value for a qualifier/condition/result. |
| `value_unit` | `string` | one | Unit (UCUM recommended). |
| `value_entity_ref` | `uriorcurie` | one | Entity-valued qualifier reference (Entity id). |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### Record

Common metadata for any record.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### Reference

A referenced/cited external work used as background or evidence.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `citation_text` | `string` | one | Citation string as appears in the paper. |
| `doi` | `string` | one | DOI string, for example 10.xxxx/xxxx. |
| `pmid` | `string` | one | PubMed ID string. |
| `url` | `uri` | one | URL for the referenced work. |
| `year` | `integer` | one | Publication year. |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### ResearchStateRecord

Current interpretation/state for one or more assertions or research branches. This is a workflow/readout layer: keep support/refute evidence in EvidenceLink.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `target_assertions` | `uriorcurie` | many | Assertions this state, next action, or execution is about. |
| `state` | `ResearchState` | one, required | Current claim or branch state. |
| `current_read` | `string` | one | Concise current interpretation of the claim after considering available evidence. |
| `rationale` | `string` | one | Explanation of why the evidence supports/refutes the assertion. |
| `recommended_next_actions` | `uriorcurie` | many | NextAction IDs recommended by a research-state record. |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### Result

A structured representation of a reported result/statistic.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `result_text` | `string` | one | Natural-language statement of the result. |
| `outcome` | `uriorcurie` | one | Entity reference for the measured outcome. |
| `comparator` | `string` | one | Comparator/control condition description. |
| `effect_size` | `float` | one | Reported effect size (if numeric). |
| `effect_size_type` | `string` | one | Effect size type, for example log2FC, odds ratio, or Cohen's d. |
| `p_value` | `float` | one | Reported p-value (if any). |
| `ci_low` | `float` | one | Lower confidence interval bound. |
| `ci_high` | `float` | one | Upper confidence interval bound. |
| `statistic` | `string` | one | Reported test or statistic, for example t-test, F statistic, or chi-square. |
| `n` | `integer` | one | Sample size for this result. |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### Study

A study described in the paper (may include multiple experiments).

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `study_type` | `uriorcurie` | one | Ontology term for study design/type (OBI/EFO recommended). |
| `study_contexts` | `Context` | many | Context objects for the study (may overlap with assertion contexts). |
| `experiments` | `Experiment` | many | Experiments/assays within a study. |
| `sample_size` | `integer` | one | Total sample size (if reported). |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### StudyCritique

A limitation/flaw/risk-of-bias assessment.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `critique_type` | `ThreatToValidityType` | one | Broad threat-to-validity class. |
| `risk_domain` | `RiskOfBiasDomain` | one | Specific risk/bias domain. |
| `severity` | `SeverityLevel` | one | Severity label. |
| `impacted_assertions` | `uriorcurie` | many | Assertions likely impacted. |
| `impacted_evidence_items` | `uriorcurie` | many | Evidence items likely impacted. |
| `mitigation_suggestions` | `string` | many | Suggested mitigations (optional). |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### TextSpan

A grounded location in a document where an extracted object is evidenced.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `document_id` | `uriorcurie` | one, required | Identifier of the source document this span belongs to. |
| `section_type` | `SectionType` | one, required | Canonical section for this span. |
| `section_heading` | `string` | one | Actual heading text, if available. |
| `start_char` | `integer` | one, required | Start character offset (0-based). |
| `end_char` | `integer` | one, required | End character offset (exclusive). |
| `exact_text` | `string` | one | Exact extracted string (optional). |
| `page_number` | `integer` | one | Page number (if PDF-sourced). |
| `artifact_ref` | `uriorcurie` | one | Optional reference to an Artifact (figure/table). |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |

### Variable

A measured/manipulated variable in an experiment.

| Slot | Range | Cardinality | Description |
|------|-------|-------------|-------------|
| `variable_role` | `string` | one | Role of the variable (independent/dependent/control/confounder). |
| `variable_entity` | `uriorcurie` | one | Entity reference (Entity id) representing what is measured/manipulated. |
| `measurement_type` | `uriorcurie` | one | Ontology term for measurement/attribute type (optional). |
| `value_text` | `string` | one | Text value for a qualifier/condition/result. |
| `value_number` | `float` | one | Numeric value for a qualifier/condition/result. |
| `value_unit` | `string` | one | Unit (UCUM recommended). |
| `text_spans` | `TextSpan` | many | Text spans grounding this object. |
| `id` | `uriorcurie` | one, required | Stable identifier for the object (URI/CURIE recommended). |
| `label` | `string` | one | Human-friendly short label. |
| `description` | `string` | one | Longer free-text description. |
| `aliases` | `string` | many | Alternative labels/synonyms. |
| `notes` | `string` | one | Curator/system notes (not intended as machine-extracted content). |
| `origin` | `Origin` | one | Whether content is explicitly author-stated or inferred. |
| `curation_status` | `CurationStatus` | one | Review status for this extracted object. |
| `confidence_score` | `float` | one | Extractor confidence (0-1). |
| `provenance` | `ProvenanceRecord` | one | Minimal provenance record. |
| `created_on` | `datetime` | one | Timestamp for object creation. |
| `created_by` | `uriorcurie` | one | Actor responsible (tool URI or ORCID). |
| `generated_by` | `uriorcurie` | one | Reference to an ExtractionActivity that generated this object. |
| `derived_from` | `uriorcurie` | many | Upstream objects this record was derived from. |
