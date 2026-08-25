# Prior-art fixture set

This directory holds CSAG extractions of three open-license manuscripts on
adjacent standards for structured scholarly knowledge. Each fixture includes
the converted Markdown, the section audit and article sidecar, the
`paper_extraction.json` artifact, and its validation and quality reports.
Two fixtures also include the source PDF because their licenses permit it.

- `ciccarese2013_pav_ontology/`: the PAV (Provenance, Authoring and
  Versioning) ontology; source PDF included.
- `soilandreyes2022_rocrate/`: RO-Crate (Research Object Crate) packaging of
  research artifacts.
- `stocker2025_machine_readable/`: machine-readable expressions of research
  findings; source PDF included.

`candidate_manifest.json` records the license evidence and the exact files
included for each fixture; `scripts/verify_prior_art_manifest.py` checks it.
Manuscripts without documented redistribution rights are cited in the CSAG
artifacts, and their sources are not included.
