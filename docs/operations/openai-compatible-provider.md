# OpenAI-Compatible Provider Operations

The adapter is offline by default and has no import-time network behavior.
Configure it through the `RESEARCH_LIBRARY_` settings namespace:

```text
RESEARCH_LIBRARY_LLM_BASE_URL=https://provider.example/v1
RESEARCH_LIBRARY_LLM_MODEL=
RESEARCH_LIBRARY_LLM_TIMEOUT_SECONDS=30
RESEARCH_LIBRARY_LLM_INCLUDE_RESPONSE_FORMAT=true
RESEARCH_LIBRARY_LLM_ALLOW_INSECURE_HTTP=false
RESEARCH_LIBRARY_LLM_API_KEY=
```

`base_url` is the API root; the client appends `/chat/completions`. URL
userinfo, query strings, fragments, and non-HTTP schemes are rejected. HTTPS
is required for remote hosts. `localhost`, `127.0.0.1`, and `::1` may use HTTP
for a local compatible server. API keys are optional; when present they are
sent only as an outbound Bearer header and are never written to traces or
audit records.

CI uses scripted transports and never accesses a provider. The default smoke
command is also offline:

```bash
python -m research_library.llm.provider_smoke
```

To intentionally make one synthetic live request, provide a model and
credentials in the environment and use `--live`. The smoke command prints
only provider, hostname, model, latency, request-ID presence, usage presence,
and structured-result status; it does not print prompts, responses, headers, or
credentials.
