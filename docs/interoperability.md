# Interoperability

CSAG preserves scientific argument structure and exposes mappings to adjacent
standards through its export formats.

## Export fidelity

| Format | Contract | Suitable for agent handoff |
|---|---|---|
| JSON | Lossless canonical artifact | Yes |
| RO-Crate (Research Object Crate) | Lossless bundle: byte-identical copies of the included files, each with a SHA-256 hash and byte count | Yes |
| JSON-LD (JSON for Linking Data) and RDF (Resource Description Framework) Turtle | Lossy semantic projection of CSAG identifiers and links | No; use for linked-data tooling |
| GraphML and TSV (tab-separated values) | Lossy analysis view with only the fields needed for graph or tabular analysis | No |

Export commands print the fidelity level. A receiving agent validates the
canonical JSON, or verifies the RO-Crate file hashes and then validates the
included `paper_extraction.json`.

## Provenance

`ExtractionActivity`, `generated_by`, `derived_from`, `created_on`, and
`created_by` map to PROV-O (the W3C Provenance Ontology) and PAV (Provenance,
Authoring and Versioning) patterns. Keep the source manuscript, schema version,
validator version, and extraction parameters with each artifact.

| CSAG field | Adjacent standard | Mapping note |
|------------|-------------------|--------------|
| `ExtractionActivity` | PROV-O `prov:Activity` | One extraction, validation, review, or export run. |
| `Execution` | PROV-O `prov:Activity` or workflow run record | A run that generated evidence, tested assertions, or produced artifacts. |
| `created_on` | PAV `pav:createdOn` | Timestamp for object creation. |
| `created_by` | PAV `pav:createdBy` | Person, service, or tool responsible for the record. |
| `generated_by` | PROV-O `prov:wasGeneratedBy` | Links records to an extraction activity. |
| `derived_from` | PROV-O `prov:wasDerivedFrom` | Links records to upstream CSAG objects or source records. |

## Evidence and entities

Evidence categories can be aligned with ECO (Evidence and Conclusion Ontology)
terms when a curator has enough detail. Entity records can carry
Biolink-compatible categories and external CURIEs (compact URIs) in `xrefs` or
`ontology_annotations`.

| CSAG field | Adjacent standard | Mapping note |
|------------|-------------------|--------------|
| `EvidenceItem.evidence_type` | ECO evidence classes | Use ECO only when the manuscript supports the specific evidence class. |
| `EvidenceLink.polarity` | SEPIO (Scientific Evidence and Provenance Information Ontology) evidence assertion relation | Keep support and refute semantics on the link, not on the evidence item. |
| `Entity.entity_category` | Biolink Model category | Map broad categories such as gene, organism, disease, or chemical to Biolink classes. |
| `Entity.xrefs` | OBO (Open Biological and Biomedical Ontology) Foundry and domain database identifiers | Store CURIEs or resolvable URIs for external database cross-references. |
| `OntologyAnnotation` | OBO, Biolink, or ECO term mapping | Records term ID, label, match type, and optional evidence code. |
| `EntityMention` | BioC or PubTator-style mention row | Keep mention offsets and normalized IDs as optional supplementary tables. |

[Entity normalization](entity-normalization.md) documents the default
biomedical entity-normalization layer and the worked supplement under
`supplementary/entity-normalization/`.

## Citations and claims

`Reference` objects can represent CiTO (Citation Typing Ontology) citation
relations. CSAG assertions can be exported as findings in the style of the Open
Research Knowledge Graph (ORKG) and its reborn articles, and CSAG keeps context,
evidence polarity, and inference steps explicit.

| CSAG field | Adjacent standard | Mapping note |
|------------|-------------------|--------------|
| `Reference` | CiTO cited entity | Captures cited works used as background or evidence. |
| `EvidenceItem.referenced_works` | CiTO citation relation target | Use with `EvidenceLink` to say how the citation bears on a claim. |
| `Assertion` | ORKG reborn finding | Export as a finding only with context and grounding retained. |
| `Context` / `Condition` | ORKG reborn qualifiers | Preserve biological and experimental scope around findings. |
| `InferenceStep` | Argumentation reasoning step | Keeps multi-premise reasoning distinct from direct evidence links. |
| `ResearchStateRecord` / `NextAction` | Lab notebook or task-handoff state | Keeps the recorded read and follow-up actions separate from evidence polarity. |

## Restricted evidence

When source text cannot be redistributed:

1. Keep stable object IDs and source document IDs.
2. Keep section labels and page numbers when redistribution permits.
3. Replace `TextSpan.exact_text` with a redacted snippet or omit it.
4. Preserve offsets only when the source document is available to the reviewer.
5. Keep validation and quality reports so downstream users can audit structure
   without receiving protected source text.

## RO-Crate packaging

`csag export --format ro-crate` packages `paper_extraction.json` with the
validation, quality, and lint reports, the Markdown files, and the article JSON
and section audit sidecars from the same directory, plus a matching
entity-normalization supplement, when those files exist. The crate metadata
records the CSAG schema and validator versions, validation profile, source
extraction identifier, extraction and execution activities, and hashes for
every copied file.

The exporter includes sidecars by presence and does not apply source-license
restrictions. When source text cannot be redistributed, create the crate from a
directory that contains only permitted files. The exporter refuses an output
directory that is not empty. If a validation, quality, or lint report does not
match its recorded input hash, the exporter stops instead of packaging that
stale report.
