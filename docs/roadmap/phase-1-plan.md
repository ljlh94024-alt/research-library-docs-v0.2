# Phase 1 Plan

Phase 1 is deliberately staged so the auditable foundation exists before any
semantic algorithm or provider boundary is introduced.

## 1A — Refinery Domain Foundation

This phase establishes normalized `ClaimGroup`, immutable
`ResolutionDecision`, explicit decision Claim/Evidence inputs,
`ConfidenceAssessment`, first-class `SourceDependency`, publication-aware
`KnowledgeAtom`, migration `0003`, repository invariants, provenance, and nine
typed stage contracts.

## 1B — Deterministic Fixture Pipeline

The following five fixtures are implemented as deterministic golden E2E
expectations:

| Fixture | Expected outcome |
| --- | --- |
| `independent_support` | Two independent sources produce high agreement and a publishable result. |
| `multi_repost_same_origin` | Ten URLs collapse to one effective unit, fail the evidence floor, and produce a `WITHHELD` atom. |
| `direct_conflict` | An open contradiction produces `CONFLICTING` resolution and a `WITHHELD` atom. |
| `qualified_support` | `QUALIFIES` remains qualifying-only, resolves to `INSUFFICIENT_EVIDENCE`, and produces a `WITHHELD` atom. |
| `snapshot_history` | Old snapshots/results remain readable after a later run. |

The implementation uses `FixtureSemanticBackend`, stable artifact IDs,
content-addressed stage manifests, and explicit versioned
Normalization/Independence/Contradiction/Resolution/Confidence/Atom policies.
It retains append-only history and offline repeatability. No migration/schema
change, real LLM, network/API call, embedding, or vector database is allowed.

## 1C — Structured LLM Boundary

Add structured request/response contracts and fake-provider fixtures only after
the deterministic pipeline is stable. Real provider calls remain outside the
offline test suite.

## 1D — Optional Real Provider

Only an explicit later decision may introduce a real provider. Credentials,
network behavior, retry policy, and usage telemetry must remain outside the
domain model.
