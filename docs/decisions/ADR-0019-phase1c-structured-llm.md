# ADR-0019: Phase 1C Structured LLM Boundary

## Status

Accepted for Phase 1C review.

## Decision

Phase 1C introduces a provider-neutral, stage-aware semantic boundary. The
LLM may generate only semantic candidates; it never chooses persistent IDs,
PipelineRun/StageRun identity, confidence, resolution status, or publication
status. Normalization, independence, contradiction, resolution, confidence,
and atom publication remain the deterministic Phase 1B tail.

Semantic calls are owned by the canonical stages that request them:

```text
evidence_extract -> evidence extraction
claim_extract    -> claim extraction
evidence_link    -> relation classification
independence     -> optional dependency signals
```

No structured call is attributed to `normalize`, `contradiction`, `resolve`,
`confidence`, or `atom_build`. The owning StageRun is persisted before the
runtime invokes a client.

## Structured execution and audit

`PromptRegistry` owns source-controlled prompt IDs and versions. `ModelRouter`
selects a static model role, and `LLMClientRegistry` selects an offline fake
client. `StructuredLLMRuntime` owns prompt rendering, strict Pydantic v2
validation with `extra="forbid"`, retries, request/response trace persistence,
and immutable per-attempt `LLMCallRecord` rows.

Malformed JSON, schema errors, unknown fields, invalid enum/range values, and
unknown references are visible failures. There is no Markdown stripping,
regex repair, prose coercion, or fixture fallback. Every attempt preserves the
same logical request ID and its own attempt number.

Trace envelopes are canonical JSON and content-addressed. Requested refs,
embedded hashes, and canonical bytes are checked on read. Trace payloads never
contain API keys, cookies, Authorization headers, credentials, or secrets.

Migration `0004_phase1_llm_audit.py` adds only `llm_calls`, with stage foreign
key, retry uniqueness, token/latency checks, and query indexes. Call-level
telemetry is authoritative; StageRun model/provider/prompt fields are only a
stage summary. Processing provenance exposes the exact calls for a stage, and
deterministic runs legitimately expose zero calls.

## Explicit non-goals

Phase 1C has no real provider, HTTP/API client, credentials, embedding, vector
database, web ingestion, agent framework, pricing table, or LLM-based
resolution, confidence, or atom publication. Those remain outside this phase.
