# Phase 1C Structured LLM Boundary

```text
existing SourceSnapshot
  -> StageRun(evidence_extract)
  -> StructuredLLMRuntime -> EvidenceCandidate
  -> StageRun(claim_extract)
  -> StructuredLLMRuntime -> ClaimCandidate
  -> deterministic normalize
  -> StageRun(evidence_link)
  -> StructuredLLMRuntime -> EvidenceRelationCandidate
  -> StageRun(independence)
  -> optional StructuredLLMRuntime -> DependencySignal
  -> deterministic contradiction -> resolution -> confidence -> atom_build
```

The runtime is deliberately offline-testable. Prompt identity, route, schema
identity, logical request, physical attempt, usage, latency, and content-
addressed request/response traces are recorded in `llm_calls`. The database
record points to filesystem traces; the LLM output is not inserted as a truth
or knowledge entity.

`FixtureHarness` remains the only fixture input seeding layer. The core
`SemanticBackend` seam consumes existing snapshot IDs and typed stage context.
`FixtureSemanticBackend` is an offline adapter, while
`StructuredLLMSemanticBackend` maps validated fake structured outputs into the
same candidate contracts.

The five Phase 1B golden policies and their deterministic outputs are frozen:
`independent_support` is `RESOLVED`/`ACTIVE`, `multi_repost_same_origin` is
`RESOLVED`/`WITHHELD`, `direct_conflict` is `CONFLICTING`/`WITHHELD`,
`qualified_support` is `INSUFFICIENT_EVIDENCE`/`WITHHELD`, and
`snapshot_history` remains append-only and readable.
