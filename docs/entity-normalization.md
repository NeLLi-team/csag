# Entity normalization

CSAG keeps scientific argument structure in the core graph and treats
biomedical entity normalization as a supplementary interoperability layer. The
schema exposes `Entity`, `OntologyAnnotation`, `EntityMention`, `xrefs`, and
context fields that point to entities. CSAG is not a biomedical entity
normalizer.

## Standard stack

Biological entity identity uses four layers:

| Layer | Standard or source | CSAG use |
|-------|--------------------|----------|
| Entity class model | Biolink Model | Map `entity_category` to broad biomedical knowledge graph classes. |
| Ontology identifiers | OBO (Open Biological and Biomedical Ontology) Foundry and domain databases | Store canonical CURIEs (compact URIs) in `xrefs` and `ontology_annotations`. |
| Identifier syntax and resolution | Identifiers.org-style CURIEs and URIs | Prefer portable compact identifiers such as `NCBITaxon:9606` or `UniProtKB:P04637`. |
| Mention exchange | BioC and PubTator-style tables | Keep mention offsets and normalized IDs in supplementary files. |

## Default category mapping

| CSAG category | Biolink class | Preferred identifiers |
|---------------|---------------|-----------------------|
| `organism`, `strain` | `biolink:OrganismTaxon` | `NCBITaxon`, optionally `GTDB` for microbial taxonomy |
| `gene`, `transcript` | `biolink:Gene` | `NCBIGene`, `HGNC`, `MGI`, `RGD`, `Ensembl` |
| `protein` | `biolink:Protein` | `UniProtKB`, `PR` |
| `variant` | `biolink:SequenceVariant` | `dbSNP`, `ClinVar`, `HGVS`, `SO` |
| `disease` | `biolink:Disease` | `MONDO`, then `DOID`, `OMIM`, `Orphanet`, `MeSH`, `UMLS` |
| `phenotype` | `biolink:PhenotypicFeature` | `HP`, `MP`, `PATO` |
| `cell_type` | `biolink:Cell` | `CL` |
| `tissue`, `anatomical_structure` | `biolink:AnatomicalEntity` | `UBERON`, `FMA`, `BTO` |
| `biological_process` | `biolink:BiologicalProcess` | `GO` |
| `molecular_function` | `biolink:MolecularActivity` | `GO` |
| `cellular_component` | `biolink:CellularComponent` | `GO` |
| `chemical`, `drug`, `metabolite` | `biolink:ChemicalEntity` | `CHEBI`, `PubChem`, `ChEMBL`, `DrugBank`, `HMDB` |
| `pathway` | `biolink:Pathway` | `Reactome`, `KEGG`, `WikiPathways` |
| `assay`, `method` | `biolink:Procedure` | `OBI`, `EFO`, `EDAM`, `NCIT` |
| `environment` | `biolink:EnvironmentalFeature` | `ENVO` |
| Evidence type (not an entity category) | ECO (Evidence and Conclusion Ontology) classes | Map from `EvidenceItem.evidence_type`, not from `Entity`. |

## Supplement files

`supplementary/entity-normalization/` holds the worked supplement for
`examples/pmid35150280`.

| File | Purpose |
|------|---------|
| `entity_profile.yaml` | Allowed namespaces, preferred namespace order, Biolink class mapping, and required fields. |
| `ontology_mappings.tsv` | Tabular mapping from CSAG `entity_category` to Biolink classes and preferred identifier namespaces. |
| `entity_catalog.tsv` | One row per normalized entity. |
| `entity_mentions.tsv` | One row per mention, with document ID, section, offsets, exact text, linked entity, confidence, extractor, and review flag. |
| `normalization_report.json` | Counts, namespace coverage, unmapped entities, ambiguous mappings, ontology versions, tools, and curator review status. |
| `example_entity_bundle.json` | JSON form of the same bundle for machine consumers. |

Minimum `entity_catalog.tsv` columns:

```text
csag_entity_id	label	entity_category	biolink_class	canonical_curie	canonical_uri	xrefs	aliases	match_type	confidence	curation_status	source_document
```

Minimum `entity_mentions.tsv` columns:

```text
mention_id	csag_entity_id	document_id	section_type	start_char	end_char	exact_text	mention_type	confidence	extractor	needs_review
```

## Validation rules

Run:

```bash
uv run python scripts/validate_entity_normalization.py
```

The validator checks that:

- catalog and mention files have the required columns
- categories match `entity_profile.yaml`
- Biolink class mappings match the category mapping in `entity_profile.yaml`
- canonical IDs and xrefs are valid CURIEs or HTTP(S) URIs
- confidence values are in `[0, 1]`
- mention offsets are ordered integers
- mention rows resolve to catalog entities
- every catalog entity has at least one mention row
- the JSON report and JSON bundle agree with the TSV counts

Unresolved or manuscript-local biological terms use a local CURIE such as
`csag.local:pmid35150280.EN0001`, set `curation_status` to `needs_review`, and
record the ambiguity in `normalization_report.json`.

## References

- [Biolink Model documentation](https://biolink.github.io/biolink-model/)
- [OBO Foundry principles](https://obofoundry.org/principles/fp-000-summary.html)
- [Identifiers.org documentation](https://docs.identifiers.org/)
- [NCBI PubTator Central API](https://www.ncbi.nlm.nih.gov/CBBresearch/Lu/Demo/PubTatorCentral/api.html)
- [NCBI BioC API](https://www.ncbi.nlm.nih.gov/research/bionlp/APIs/BioC-PMC/)
