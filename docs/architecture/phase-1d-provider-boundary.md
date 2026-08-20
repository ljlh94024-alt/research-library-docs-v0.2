# Phase 1D Provider Boundary

```text
ModelRouter(task) -> ModelTarget(provider, model)
                         |
                  LLMClientRegistry
                         |
             OpenAICompatibleClient
                         |
      HTTPTransport (stdlib production / scripted test)
                         |
              chat-completions envelope
                         |
              StructuredLLMRuntime validation
                         |
    Evidence / Claim / Relation / Dependency candidates
                         |
      deterministic tail: normalize -> contradiction
              -> resolve -> confidence -> atom_build
```

The client has no semantic schema imports and no internal retry. Every physical
attempt is persisted by the runtime as one `LLMCallRecord`; retryable provider
errors are retried by the runtime, while authentication, configuration,
redirect, size, truncation, and content-filter errors stop immediately.

The provider request contains only model, messages, temperature, and the
optional JSON response-format hint. Runtime metadata such as logical request
IDs is not sent to the provider. Safe response provenance is limited to the
provider request ID, HTTP status, finish reason, and normalized usage.
