# License policy

The repository releases its schema, scripts, documentation, examples, and
generated CSAG artifacts under the BSD 3-Clause License unless a file or source
manuscript states a different license. `LICENSE` holds the license text and
the Berkeley Lab copyright notice.

| Exception | License policy |
|-----------|----------------|
| Source manuscripts and third-party PDFs | Keep their original licenses. Redistribute them only when the source license permits it. |
| Generated CSAG artifacts derived from a source manuscript | BSD 3-Clause License unless the source manuscript license restricts redistribution. |

Prior-art fixtures listed in `examples/prior-art/candidate_manifest.json` are
released only with documented open licenses. Each released fixture records
Creative Commons license evidence in its example manifest, and two fixtures
(`ciccarese2013_pav_ontology` and `stocker2025_machine_readable`) bundle the
source PDF their licenses permit. The `examples/jamy2026` example follows the
same rule. The manuscript
[10.1038/s41467-025-67401-4](https://doi.org/10.1038/s41467-025-67401-4)
reports a Creative Commons Attribution 4.0 International license, recorded in
`examples/jamy2026/example_manifest.json`.

Before adding a fixture, check its source license and record the license
status and allowed files in the fixture's manifest and README.
