# Phase 1 Entry Notes

These notes record supervisor observations for the next phase. They are not
implemented by the Phase 0 freeze work.

## Resolution status vocabulary

ADR-0009 and `ResolvedClaimStatus` use different vocabularies. Before a Phase 1
Claim Resolution stage, formally unify `resolved`, `unresolved`, `conflicting`,
`insufficient_evidence`, `historical_change`, and any replacement values.

## KnowledgeAtom expansion

Phase 0 keeps KnowledgeAtom as a minimal skeleton. Phase 1 should decide how to
add subject, predicate, object, status, validity, and richer provenance without
weakening the existing storage boundary.

## Resolution decision provenance

The current chain identifies the candidate ClaimGroup and its members. Phase 1
needs explicit relations for selected, supporting, rejected, and contradicting
claims/evidence used by a resolver.

## Confidence components

ADR-0006 calls for score components and reasons. Phase 1 should define their
structure and persistence location before implementing a ConfidenceEngine.

## SourceDependency boundary

The database table exists, but the Domain and Repository boundary is incomplete.
Complete it before implementing Source Independence.

## LLM structured outputs and telemetry

The Phase 0 FakeLLM boundary is sufficient. Phase 1 may add structured response
schemas, provider/model routing, usage, latency, request IDs, and prompt
versions; no real provider is introduced here.
