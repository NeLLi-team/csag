# Repository layout

```text
csag/
├── README.md
├── AGENTS.md          # operating contract for extraction agents
├── CHANGELOG.md
├── CITATION.cff
├── .zenodo.json
├── LICENSE
├── mkdocs.yml
├── pyproject.toml
├── uv.lock
├── csag/              # command-line interface and Python API
├── skills/            # two skills, authoritative LinkML schema, generated JSON Schema
├── schema/            # generated Markdown schema documentation
├── scripts/           # checks, figure generation, and the local OCR helper
├── docs/              # MkDocs documentation
├── examples/          # redistributable example artifacts and manifests
├── tests/             # test suite and fixtures
└── supplementary/     # entity-normalization supplement
```

`skills/` holds the `pdf-to-md` and `csag-extraction` skills. The
authoritative LinkML (Linked Data Modeling Language) schema
`skills/csag-extraction/assets/csag.yaml` and the JSON Schema files generated
from it are in the `csag-extraction` skill's `assets/` directory; `schema/`
holds the Markdown documentation generated from the same source.

`csag ingest` writes to the directory named by `--output-dir`, or to
`work/<stem>/` under the repository root when the option is omitted. Work
directories are local working data and are not tracked.
