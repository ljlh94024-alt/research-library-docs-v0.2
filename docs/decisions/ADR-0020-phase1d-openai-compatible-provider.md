# ADR-0020 — Phase 1D OpenAI-Compatible Provider Boundary

## Decision

Phase 1D adds a provider-neutral boundary around the OpenAI-compatible
`POST /chat/completions` envelope. `OpenAICompatibleClient` implements the
existing `LLMClient.complete(LLMRequest) -> LLMResponse` protocol and uses an
injectable standard-library HTTP transport. The production transport validates
TLS normally, does not follow redirects, bounds response reads, and performs no
retry. One `complete()` call is exactly one physical HTTP request.

`StructuredLLMRuntime` owns all retry decisions. A provider call may produce
semantic candidates only for evidence extraction, claim extraction, evidence
linking, and independence. The deterministic normalization, contradiction,
resolution, confidence, and atom stages remain authoritative.

Provider telemetry is kept in the existing immutable `llm_calls` audit record's
`metadata`; no migration `0005` or provider-specific table is added. API keys
are optional, represented as `SecretStr`, and never enter request traces,
audit metadata, errors, logs, or response bodies. Remote HTTP is rejected by
default; loopback HTTP is allowed for local compatible servers.

## Rejected alternatives

- OpenAI SDK or another provider SDK: adds provider lock-in and a runtime dependency.
- Provider-internal retry: makes one audit record ambiguous across physical requests.
- Provider-specific database fields: violates the frozen `0004` audit schema.
- LiteLLM as a required core dependency: expands the dependency and routing boundary.
- LLM resolution, confidence, atom publication: violates deterministic-tail ownership.
- Dynamic smart routing, pricing, streaming, tool calling, and async rewrites: out of scope.

## Operational contract

The adapter validates only the standard chat-completions envelope. Strict JSON
and Pydantic semantic validation remain in `StructuredLLMRuntime`; no markdown
or regex repair is performed. `response_format` can be disabled for compatible
servers that do not support it. The optional live smoke command is opt-in and
sends only a synthetic prompt.
