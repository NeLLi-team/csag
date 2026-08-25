# Entity normalization supplement

This directory is a worked entity-normalization package for
`examples/pmid35150280/paper_extraction.json`. It shows how CSAG entities map
to Biolink Model classes, to Open Biological and Biomedical Ontology (OBO)
style or database compact URIs (CURIEs), and to mention-level annotations
without extending the core CSAG schema beyond its argument-graph role.
`docs/entity-normalization.md` describes the profile and the validation
rules.

Validate the package:

```bash
uv run python scripts/validate_entity_normalization.py
```

Files:

- `entity_profile.yaml`: allowed namespaces and category mappings
- `ontology_mappings.tsv`: the profile mapping as a table
- `entity_catalog.tsv`: normalized entities from the PMID 35150280 example
- `entity_mentions.tsv`: mention-level rows linked to catalog entities
- `normalization_report.json`: coverage and review-status summary
- `example_entity_bundle.json`: JSON form of the same supplement
