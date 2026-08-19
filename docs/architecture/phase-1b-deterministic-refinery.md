# Phase 1B Deterministic Knowledge Refinery

Phase 1B is the offline implementation of the canonical nine-stage refinery:

```text
evidence_extract -> claim_extract -> normalize -> evidence_link
-> independence -> contradiction -> resolve -> confidence -> atom_build
```

`FixtureSemanticBackend` is the only semantic input boundary in this phase.
It serves the five frozen golden fixtures without network, API, LLM, embedding,
or vector-store access. `DeterministicRefinery` persists every formal domain
object through the existing Phase 1A repository and supplies the canonical
stage owner for each output.

IDs are content-derived through `stable_artifact_id`. Stage outputs are
described by immutable `StageManifest` values whose IDs are SHA-256 hashes of
canonical JSON payloads. The pipeline and stage run IDs include fixture,
pipeline version, and run key. A successful replay therefore produces the
same artifact and manifest IDs while respecting the repository's terminal
lifecycle rules.

The five golden fixtures cover independent agreement, shared-origin repost
collapse, direct contradiction withholding, conditional qualification, and
append-only snapshot history. Confidence reasons include effective source
independence, evidence relation, agreement, extraction confidence, and any
contradiction penalty. Atom publication requires a resolved decision and a
met evidence floor; qualified evidence remains conditional.

Phase 1C is not part of this implementation.
