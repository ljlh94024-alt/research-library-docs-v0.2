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

Phase 1C adds the stage-aware `SemanticBackend` v2 seam, strict Pydantic
schemas, source-controlled Prompt Registry, static ModelRouter, offline fake
client registry, StructuredLLMRuntime, content-addressed request/response
traces, and immutable `LLMCallRecord` audit persistence in migration `0004`.
Calls are owned only by `evidence_extract`, `claim_extract`, `evidence_link`,
and optional `independence`. Deterministic Resolution, Confidence, and Atom
publication remain unchanged. Real providers, credentials, network/API,
embedding/vector DB, and Phase 1D features remain out of scope.

## 1D — Optional Real Provider

Phase 1D introduces an optional OpenAI-compatible provider adapter. Credentials,
network behavior, retry policy, and usage telemetry remain outside the domain
model; CI remains fully offline and the deterministic tail remains unchanged.
