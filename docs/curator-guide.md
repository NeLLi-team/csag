# Curator guide

Preserve the author's meaning and make the argumentation graph explicit.

## Assertions

Write assertions that are complete, scoped, and close to the manuscript's
wording. Give every assertion at least one context. Use `criticality` to
separate core and major assertions from supporting and background statements,
and add `falsification_criteria` to core and major assertions.

Keep support and refutation out of the assertion text. Polarity belongs only
in `EvidenceLink`.

Good:

```json
{
  "assertion_text": "Blue light increased plastid pigment absorbance relative to dark controls.",
  "claim_role": "conclusion",
  "criticality": "core",
  "normalization_status": "raw",
  "contexts": [
    {
      "id": "csag:context/csag:doc/toy_plastid_claim/C0001",
      "label": "toy algae cultures under blue-light or dark-control growth conditions",
      "context_facet": "model_system"
    }
  ],
  "falsification_criteria": [
    "The claim would be weakened if independent blue-light cultures did not show higher absorbance than dark controls."
  ]
}
```

Avoid (evidence semantics in the assertion text, and no context):

<!-- csag-snippet-ignore: invalid counterexample -->
```json
{
  "assertion_text": "Supported by Figure 1, blue light increased plastid pigment absorbance.",
  "claim_role": "conclusion",
  "contexts": []
}
```

## Contexts

State the scope under which the assertion or evidence holds. Start coarse
when the manuscript gives no detail, then refine to the organism, tissue,
cell type, disease state, environment, or experimental setting that the
manuscript supports.

Good:

```json
{
  "id": "csag:context/csag:doc/toy_plastid_claim/C0001",
  "label": "toy algae cultures under blue-light or dark-control growth conditions",
  "context_facet": "model_system"
}
```

Avoid a vague label such as `paper` when the source gives a more specific
experimental or biological scope.

## Evidence links

An evidence item states what the manuscript observed, measured, modeled, or
cited. An evidence link states how that evidence bears on an assertion.

Good:

```json
{
  "evidence_item": "csag:evidence/csag:doc/toy_plastid_claim/E0001",
  "assertion": "csag:assertion/csag:doc/toy_plastid_claim/A0002",
  "polarity": "supports",
  "strength": "moderate",
  "rationale": "The measured absorbance increase directly supports the treatment-control claim."
}
```

Do not write `"supports"` into `EvidenceItem.description` or
`Assertion.assertion_text`. Polarity in free text is harder to query and
breaks the graph pattern.

## Critiques and gaps

Use `StudyCritique` for validity threats and limitations. Use `KnowledgeGap`
for open questions, missing experiments, unresolved mechanisms, and future
work. Link critiques and gaps to the affected assertions or evidence items
when you can.

Good critique:

```json
{
  "critique_type": "external_validity",
  "risk_domain": "other",
  "severity": "moderate",
  "description": "The result is based on one toy experiment and needs independent replication.",
  "impacted_assertions": ["csag:assertion/csag:doc/toy_plastid_claim/A0002"]
}
```

Good knowledge gap:

```json
{
  "gap_type": "missing_mechanism",
  "description": "The mechanism connecting blue light to pigment accumulation is not tested.",
  "related_assertions": ["csag:assertion/csag:doc/toy_plastid_claim/A0002"]
}
```

## Research state and executions

Use `ResearchStateRecord` for the current read on a claim after you review
its evidence. Use `NextAction` for the next experiment, analysis, review,
branch, or decision. Use `Execution` for a run that produced inspectable
outputs or tested a claim. These objects record review state; they do not
replace evidence links.

Good current-read record:

```json
{
  "id": "csag:state/csag:doc/toy_plastid_claim/RS0001",
  "target_assertions": ["csag:assertion/csag:doc/toy_plastid_claim/A0002"],
  "state": "needs_replication",
  "current_read": "The treatment effect is supported by one experiment but needs independent replication.",
  "recommended_next_actions": ["csag:action/csag:doc/toy_plastid_claim/NA0001"]
}
```

Good next action:

```json
{
  "id": "csag:action/csag:doc/toy_plastid_claim/NA0001",
  "action_type": "replication",
  "description": "Repeat the blue-light treatment with independent cultures and blinded absorbance measurements.",
  "target_assertions": ["csag:assertion/csag:doc/toy_plastid_claim/A0002"],
  "priority": "moderate"
}
```

Good execution record (the `command` value is a placeholder):

```json
{
  "id": "csag:execution/csag:doc/toy_plastid_claim/EX0001",
  "execution_type": "analysis script",
  "execution_status": "completed",
  "command": "python analyze_absorbance.py",
  "generated_evidence_items": ["csag:evidence/csag:doc/toy_plastid_claim/E0001"],
  "tested_assertions": ["csag:assertion/csag:doc/toy_plastid_claim/A0002"]
}
```

Use `AssertionRelation` values such as `competes_with`, `alternative_to`, and
`merged_into` when several hypotheses explain the same observation. Do not
put mutually exclusive claims into one assertion.

## Text spans

Give assertions, evidence items, critiques, and gaps character offsets into
the canonical Markdown. Compute the offsets from the Markdown in the work
directory that the extraction refers to.

Do not fabricate offsets. If the source text is unavailable or cannot be
redistributed, omit or redact `exact_text` and keep enough provenance for a
curator with source access to check the span.
