# Phase 1B Deterministic Knowledge Refinery

Phase 1B is the offline implementation of the canonical nine-stage refinery:

```text
evidence_extract -> claim_extract -> normalize -> evidence_link
-> independence -> contradiction -> resolve -> confidence -> atom_build
```

`SemanticBackend` is the provider-neutral semantic input boundary in this
phase. `FixtureSemanticBackend` implements it for the five frozen golden
fixtures without network, API, LLM, embedding, or vector-store access.
`DeterministicRefinery` persists every formal domain object through the
existing Phase 1A repository and supplies the canonical stage owner for each
output.

Input Source/Snapshot records are seeded before the PipelineRun. IDs for
formal stage outputs are namespaced by their owning StageRun. Normal runs are
append-only and receive new PipelineRun/StageRun/artifact IDs; an explicit
recovery key enables deterministic retry of one run. Stage inputs and outputs
are persisted in `StageManifestStore` as SHA-256-addressed canonical JSON and
verified on read.

The five golden fixtures cover independent agreement, shared-origin repost
collapse with a false floor, direct contradiction withholding, QUALIFIES-only
insufficient evidence, and two-run append-only snapshot history. Confidence
reasons include effective source independence, evidence relation, agreement,
deterministic freshness, extraction confidence, and contradiction penalty.
Atom publication requires a resolved decision, a met evidence floor, and
confidence at least 0.75; QUALIFIES-only evidence is withheld.

Phase 1C is not part of this implementation.
