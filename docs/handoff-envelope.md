# HandoffEnvelope reference

`HandoffEnvelope` is the exchange root for work performed by agents over CSAG
artifacts. It references content-hashed `PaperExtraction` snapshots and keeps
workflow state outside the manuscript-local extraction.

Each envelope revision is immutable by convention. A state change is recorded
as a separate `revision` with the immediate prior revisions in `parents`.

## Root fields

| Field | Cardinality | Contract |
|-------|-------------|----------|
| `id` | one, required | Stable workspace or handoff identifier. |
| `envelope_version` | one, required | Supported handoff contract version: `1.0.0`. |
| `revision` | one, required | Stable revision identifier, not a digest of the envelope bytes. |
| `parents` | many | Immediate parent revision identifiers. |
| `source_artifacts` | one or more | Content-hashed source snapshots, including at least one `paper_extraction`. |
| `assessments` | many | Agent assessments with artifact, source-object, or execution bases. |
| `actions` | many | Owned work items with status, dependencies, and acceptance criteria. |
| `executions` | many | Runs tied to actions, including content-hashed inputs and outputs. |
| `conflicts` | many | Open or resolved disagreements between revision heads. |
| `current_heads` | one or more | Revisions that head the workspace. |
| `created_on`, `created_by` | one each, required | Revision timestamp and responsible actor. |

## Content identity

Every `HandoffArtifactDigest` records:

| Field | Requirement |
|-------|-------------|
| `id` | Globally unique within the envelope. |
| `artifact_role` | Controlled role such as `paper_extraction`, `code`, or `result`. |
| `artifact_path` | Bundle-relative path or external locator. |
| `sha256` | Lowercase, 64-character SHA-256 digest. |
| `media_type`, `byte_size` | Optional media type and byte count. |

Repeated occurrences of one `artifact_path` carry the same hash and byte size.
The handoff validator resolves bundle-relative paths against the envelope
directory, verifies local bytes, and records every verified local artifact in
the validation report's `inputs` map. It rejects absolute paths, `file:`
locators, and relative paths that escape the bundle. It does not fetch
external locators that are not files; they keep their declared content
identity.

A local `paper_extraction` snapshot conforms to the closed `PaperExtraction`
schema and has a fresh local validation report with `ok: true`. Validation and
quality reports link back to a declared source-extraction digest, and every
locally resolvable report input matches its recorded hash.

### Trust boundary

Version 1.0 does not content-address or sign the envelope itself. The validator
checks revision relationships, but it cannot prove that two envelopes carrying
the same `revision` have identical bytes or that a named agent created them.
Artifact hashes protect referenced inputs and outputs, not the history record
around them. When revision integrity or actor authenticity matters, store the
envelope in a content-addressed repository and exchange its digest or signature
through that repository's trust layer.

## Assessments

An assessment records `assessment_status`, `assessment_text`, its creator, and
its timestamp. It cites at least one of:

- `basis_artifacts`: artifact digest IDs in the envelope
- `basis_refs`: IDs inside source artifacts, such as assertions or evidence items
- `basis_executions`: execution IDs in the envelope

The validator resolves artifact and execution bases locally. When a local,
hash-matching `paper_extraction` snapshot is available, it also resolves
`basis_refs`, `target_assertions`, and `target_knowledge_gaps` against that
snapshot. References into remote-only snapshots stay anchored by the declared
content hash and cannot be dereferenced locally.

## Actions and executions

Every action has one `owner`, one `action_status`, and at least one measurable
`acceptance_criteria` entry. `dependencies` resolve to other actions in the same
envelope and form an acyclic graph.

Each execution references one action through `action_ref`. It records hashed
inputs, an environment lockfile locator and digest, and the code revision. A
published handoff uses the exact commit; a development fixture may use an
explicit `uncommitted-tree-based-on:<commit>` descriptor. The validator
verifies a local environment lockfile and includes it in the report's `inputs`
map. Terminal runs record `completed_on` and `execution_outcome`; completed
runs also record at least one hashed output. A completed action requires a
linked completed execution.

## Revision heads and conflicts

`current_heads` identifies the revisions that an agent may extend. When no
conflict is open, the envelope's `revision` is a current head. An open conflict
lists at least two `competing_heads`, all of which are current heads. A resolved
conflict records `resolution` and a `resolved_by_head` that appears in
`current_heads`.

## Validation

Validate the worked two-agent fixture against the LinkML (Linked Data Modeling
Language) root:

```bash
uv run linkml-validate \
  -s skills/csag-extraction/assets/csag.yaml \
  -C HandoffEnvelope \
  tests/fixtures/handoff/two_agent_handoff.valid.json
```

Run the semantic handoff profile through the CLI:

```bash
uv run csag validate \
  tests/fixtures/handoff/two_agent_handoff.valid.json \
  --profile handoff \
  --report-out /tmp/two_agent_handoff.validation.json
```

The closed JSON Schema is
`skills/csag-extraction/assets/csag.handoff.schema.json`. The fixture contains
two agent-owned actions and executions, a two-parent merge revision, and a
resolved conflict. The fixture directory is self-contained. It includes the
source extraction, Markdown, article sidecar, validation report, quality
report, and environment lockfile that the envelope references.
