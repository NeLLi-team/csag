# Examples

Each directory holds one worked Conditional Scientific Argumentation Graph
(CSAG) example with an `example_manifest.json` that records the source,
license, included files, validation profile, and interpretation. `csag
check-examples` validates, reports, and lints every example and verifies its
manifest; the repository README gives the full command.

| Directory | Source and license | Included files |
|---|---|---|
| `toy/` | Synthetic minimal manuscript. Repository license. | Markdown, `toy_measurements.tsv`, section audit, article sidecar, CSAG, validation report, quality report. |
| `lite/` | Synthetic CSAG Lite example validated with the `lite` profile. Repository license. | Markdown, article sidecar, CSAG, validation report, quality report. |
| `pmid35150280/` | "Giant Viruses Encode Actin-Related Proteins", Molecular Biology and Evolution, DOI 10.1093/molbev/msac022. CC BY-NC 4.0. | CSAG, validation report, quality report. The Markdown and sidecars are not included. |
| `jamy2026/` | Jamy 2026, Nature Communications, DOI 10.1038/s41467-025-67401-4. CC BY 4.0. | Source PDF, Markdown, section audit, article sidecar, CSAG, validation report, quality report. |
| `prior-art/ciccarese2013_pav_ontology/` | Ciccarese 2013, PAV ontology, DOI 10.1186/2041-1480-4-37. CC BY 2.0. | Source PDF, Markdown, section audit, article sidecar, CSAG, validation report, quality report. |
| `prior-art/soilandreyes2022_rocrate/` | Soiland-Reyes 2022, RO-Crate, DOI 10.3233/DS-210053. CC BY 4.0. | Markdown, section audit, article sidecar, CSAG, validation report, quality report. |
| `prior-art/stocker2025_machine_readable/` | Stocker 2025, machine-readable research findings, DOI 10.1038/s41597-025-04905-0. CC BY 4.0. | Source PDF, Markdown, section audit, article sidecar, CSAG, validation report, quality report. |

`prior-art/candidate_manifest.json` lists the three prior-art fixtures with
their license evidence, and `coverage_metrics.json` summarizes object counts
and coverage across all examples.

## File names

Within an example, `<stem>` is the manuscript stem:

- `<stem>.md`: canonical Markdown
- `<stem>.section_audit.json`: section audit
- `<stem>.article.json`: article sidecar
- `paper_extraction.json`: the CSAG
- `paper_extraction.validation.json`: validator report
- `paper_extraction.quality.json`: quality report
- `example_manifest.json`: source, license, and included-file record

Add converted Markdown or a derived CSAG only when the source license permits
redistribution of adapted material or the manifest documents the
rightsholder's permission.
