# Conditional Scientific Argumentation Graphs

A Conditional Scientific Argumentation Graph (CSAG) is a machine-readable
representation of the argumentation structure of a scientific manuscript. It
decomposes the manuscript into assertions scoped by contexts, evidence items,
evidence links that carry support or refute polarity, study critiques,
knowledge gaps, and provenance, with each of these objects grounded to text
spans in the source. Optional modules add biological entity normalization,
reasoning chains, research-state records, and benchmark answer keys.

This repository provides the schema, the validator, the `csag` command-line
tools, worked examples, benchmark summaries, and this documentation.

## Start here

Read [CSAG Lite](csag-lite.md) first. It describes the smallest valid artifact
and the staged workflow that produces one. The pages, in the order of the
navigation:

- [CSAG Lite](csag-lite.md): the six-object subset and the staged workflow
  from manuscript to exported artifact.
- [Curator guide](curator-guide.md): how to write assertions, contexts,
  evidence links, critiques, gaps, research-state objects, and text spans.
- [Repository layout](repository-layout.md): what each directory holds.
- [Developer guide](developer-guide.md): schema regeneration, the staged
  commands, the Python API, validators, and exporters.
- [Schema table](schema-table.md): the object classes and their slots, by
  module.
- [Validation profiles](profiles.md): the `core`, `bio`, `reasoning`,
  `research_state`, and `benchmark` modules, the profiles that select them,
  and failure severities.
- [Extraction density targets](extraction-density-targets.md): how much a
  well-covered extraction contains for each document scope.
- [Entity normalization](entity-normalization.md): how to map entities to
  Biolink categories and ontology identifiers.
- [Agent handoff envelope](handoff-envelope.md): the `HandoffEnvelope` record
  that agents exchange.
- [Interoperability](interoperability.md): export fidelity and mappings to
  provenance, evidence, entity, and citation standards.
- [Adjacent standards](adjacent-standards.md): how CSAG relates to packaging,
  provenance, and research-finding standards.
- [Evaluation metrics](evaluation-metrics.md): the planned metric families.
- [Benchmark support](benchmark-support.md): answer keys and scoring.
- [License policy](license-policy.md): licenses for repository content and
  source manuscripts.
- [Release process](release-process.md): local checks, tagging, and archiving.

## Core contract

Every assertion has at least one context. Support and refutation are recorded
on evidence links, not in assertion or evidence text. Core and major
assertions are grounded to text spans and carry `falsification_criteria`, the
observation that would weaken or overturn the claim.

The bio, reasoning, research_state, and benchmark modules are optional; a
paper-local extraction validates without them. For agent-to-agent exchange, use the
separate [`HandoffEnvelope`](handoff-envelope.md) root instead of
research-state objects. [Validation profiles](profiles.md) lists the modules
and the profiles that select them.
