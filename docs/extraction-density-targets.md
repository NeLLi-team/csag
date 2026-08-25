# Extraction density targets

Density targets describe how much a well-covered extraction contains for a
given kind of source; `csag validate` checks structure. `csag report` reports
density as part of completeness and warns when an extraction is under the
target for its scope, so a thin but valid draft passes validation and the
quality report shows what is missing.

## Targets by document scope

| Document scope | Assertions | Evidence links | Contexts | Artifacts | Datasets |
| --- | --- | --- | --- | --- | --- |
| `lite` | at least 1 | at least 1 | at least 1 | optional | optional |
| `short_note` | at least 2 | at least 2 | at least 1 | if captions are present | if data-availability signals are present |
| `full_article` | at least 5 | at least 1 per core or major assertion; target 2 per core assertion | at least 2 | if captions are present | if data-availability signals are present |
| `benchmark_key` | all answer-key assertions | decisive (`supports`, `refutes`, or `mixed`) evidence for answer-key assertions | one per assertion | if captions are present | if data-availability signals are present |

Artifact and dataset targets depend on signals in the source. For every scope
except `lite`, the artifact check expects `Artifact` objects only when the
source shows figure or table captions, and the dataset check expects `Dataset`
objects only when the source shows data-availability or accession signals. A
short note with no figures and no accessions is not asked for either.

## Document scopes

`csag report --document-scope` selects the row that applies:

`lite`
:   Toy and demo extractions. One assertion, one evidence link, one context.

`short_note`
:   Short notes, editorials, and brief communications. Two assertions and two
    evidence links when the source carries them, with contexts on the
    assertions.

`full_article`
:   Full research articles. Several assertions, several contexts, and evidence
    behind every core or major assertion.

`benchmark_key`
:   Answer keys. Every answer-key assertion is present, answer-key assertions
    carry decisive evidence, and every assertion has a context.

`auto`
:   The default. An extraction with two or fewer assertions, or a source under
    1,500 words, resolves to `lite`; anything else resolves to `full_article`.
    The report records the resolved scope.

## Advisory and strict checks

Each density check reports `pass` or `warn` and carries a strict-failure flag.
By default, `csag report` is advisory. An under-target extraction gets a
`warn`, the report summarizes density, and the command exits zero.

With `--strict`, every failed check that carries the strict-failure flag
becomes a blocking issue, and the command exits non-zero. A `full_article`
extraction with one assertion warns by default and fails under `--strict`.
The strict checks are the assertion and context floors for `short_note`,
`full_article`, and `benchmark_key`, the evidence-link floors for
`short_note` and `benchmark_key`, and the caption and data-availability signal
checks.

Three checks stay advisory under `--strict`:

- The `lite` checks. A small Lite extraction passes under `--strict` and is not
  penalized for size.
- The `full_article` check that every core or major assertion has an evidence
  link. Partial extractions and reference examples often leave an assertion
  without an extracted link.
- The `full_article` target of two evidence links per core assertion. A second
  independent evidence link is not always available in the source.

Draft against `lite`, switch to the matching scope (`short_note`,
`full_article`, or `benchmark_key`) as the extraction fills out, and add
`--strict` when the extraction is meant to be complete.
