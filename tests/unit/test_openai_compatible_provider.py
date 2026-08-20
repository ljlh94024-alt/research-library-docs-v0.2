import json

import pytest

from research_library.llm import (
    HTTPResponse,
    LLMProviderError,
    LLMRequest,
    OpenAICompatibleClient,
    OpenAICompatibleConfig,
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderConnectionError,
    ProviderContentFilterError,
    ProviderHTTPError,
    ProviderProtocolError,
    ProviderRedirectError,
    ProviderRequestTooLargeError,
    ProviderResponseTooLargeError,
    ProviderTruncatedResponseError,
    ScriptedHTTPTransport,
)


def response(
    payload: object,
    *,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> HTTPResponse:
    return HTTPResponse(status, headers or {}, json.dumps(payload).encode())


def valid_payload(content: str = '{"items": []}', *, usage: object | None = None) -> dict:
    payload = {
        "id": "chatcmpl-test",
        "model": "model-returned",
        "choices": [
            {"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
    }
    if usage is not None:
        payload["usage"] = usage
    return payload


def client(script, **kwargs):
    transport = ScriptedHTTPTransport(script)
    kwargs.setdefault("api_key", "SUPER_SECRET_PHASE1D_TEST_KEY_987654321")
    config = OpenAICompatibleConfig(base_url="http://127.0.0.1:1234/v1", **kwargs)
    return OpenAICompatibleClient(config, transport=transport), transport


def test_request_serialization_and_optional_authentication() -> None:
    adapter, transport = client([response(valid_payload(), headers={"X-Request-ID": "req-1"})])
    result = adapter.complete(
        LLMRequest(
            prompt="user prompt",
            system_prompt="system prompt",
            model="requested-model",
            metadata={"logical_request_id": "must-not-be-sent"},
        )
    )
    request = transport.requests[0]
    payload = json.loads(request.body)
    assert request.method == "POST"
    assert request.url == "http://127.0.0.1:1234/v1/chat/completions"
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["Accept"] == "application/json"
    assert request.headers["Authorization"].startswith("Bearer ")
    assert payload == {
        "model": "requested-model",
        "messages": [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user prompt"},
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
    }
    assert "logical_request_id" not in request.body.decode()
    assert result.raw == {
        "request_id": "chatcmpl-test",
        "http_status": 200,
        "finish_reason": "stop",
        "provider_request_id_header": "req-1",
    }


def test_system_message_and_response_format_can_be_disabled_and_key_is_optional() -> None:
    adapter, transport = client(
        [response(valid_payload())],
        api_key=None,
        include_response_format=False,
    )
    adapter.complete(LLMRequest(prompt="prompt", model="model"))
    request = transport.requests[0]
    payload = json.loads(request.body)
    assert "Authorization" not in request.headers
    assert payload["messages"] == [{"role": "user", "content": "prompt"}]
    assert "response_format" not in payload


@pytest.mark.parametrize("status", [400, 404, 405, 413, 422, 499])
def test_unknown_and_client_http_errors_are_non_retryable(status: int) -> None:
    adapter, _transport = client([response({"error": {"message": "bad"}}, status=status)])
    with pytest.raises(ProviderHTTPError) as caught:
        adapter.complete(LLMRequest(prompt="prompt", model="model"))
    assert caught.value.retryable is False
    assert caught.value.status_code == status


@pytest.mark.parametrize("status", [408, 409, 425, 429, 500, 502, 503, 504, 599])
def test_transient_http_errors_are_retryable(status: int) -> None:
    adapter, _transport = client([response({"error": {"message": "retry"}}, status=status)])
    with pytest.raises(LLMProviderError) as caught:
        adapter.complete(LLMRequest(prompt="prompt", model="model"))
    assert caught.value.retryable is True
    assert caught.value.status_code == status


def test_401_is_typed_and_redirect_is_never_followed() -> None:
    adapter, transport = client(
        [
            response({"error": {"message": "invalid key"}}, status=401),
            response(valid_payload()),
        ]
    )
    with pytest.raises(ProviderAuthenticationError):
        adapter.complete(LLMRequest(prompt="prompt", model="model"))
    assert transport.send_count == 1

    redirect_adapter, redirect_transport = client(
        [HTTPResponse(302, {"Location": "https://redirect.example/v1/chat/completions"}, b"")]
    )
    with pytest.raises(ProviderRedirectError):
        redirect_adapter.complete(LLMRequest(prompt="prompt", model="model"))
    assert redirect_transport.send_count == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": 1}}]},
        {"choices": [{"message": {"content": ""}}]},
    ],
)
def test_invalid_envelopes_are_provider_protocol_errors(payload: dict) -> None:
    adapter, _transport = client([response(payload)])
    with pytest.raises(ProviderProtocolError):
        adapter.complete(LLMRequest(prompt="prompt", model="model"))


def test_usage_is_normalized_without_estimation() -> None:
    adapter, _transport = client(
        [response(valid_payload(usage={"prompt_tokens": 10, "completion_tokens": 5}))]
    )
    assert adapter.complete(LLMRequest(prompt="prompt", model="model")).usage == {
        "input_tokens": 10,
        "output_tokens": 5,
    }
    no_usage, _transport = client([response(valid_payload())])
    assert no_usage.complete(LLMRequest(prompt="prompt", model="model")).usage == {}


def test_finish_reason_is_not_sent_to_semantic_validation() -> None:
    adapter, _transport = client(
        [response({"choices": [{"message": {"content": "x"}, "finish_reason": "length"}]} )]
    )
    with pytest.raises(ProviderTruncatedResponseError) as caught:
        adapter.complete(LLMRequest(prompt="prompt", model="model"))
    assert caught.value.retryable is False


def test_content_filter_and_connection_errors_are_typed_and_safe() -> None:
    adapter, _transport = client(
        [response({"choices": [{"message": {"content": "x"}, "finish_reason": "content_filter"}]})]
    )
    with pytest.raises(ProviderContentFilterError) as filtered:
        adapter.complete(LLMRequest(prompt="prompt", model="model"))
    assert filtered.value.retryable is False

    adapter, _transport = client([ConnectionResetError("reset")])
    with pytest.raises(ProviderConnectionError) as connection:
        adapter.complete(LLMRequest(prompt="prompt", model="model"))
    assert connection.value.retryable is True


def test_provider_error_redacts_bearer_and_api_key_forms() -> None:
    adapter, _transport = client(
        [
            response(
                {
                    "error": {
                        "message": (
                            "Authorization: Bearer SUPER_SECRET_PHASE1D_TEST_KEY_987654321 "
                            "api_key=SUPER_SECRET_PHASE1D_TEST_KEY_987654321"
                        )
                    }
                },
                status=401,
            )
        ]
    )
    with pytest.raises(ProviderAuthenticationError) as caught:
        adapter.complete(LLMRequest(prompt="prompt", model="model"))
    assert "SUPER_SECRET_PHASE1D_TEST_KEY_987654321" not in str(caught.value)
    assert "SUPER_SECRET_PHASE1D_TEST_KEY_987654321" not in repr(caught.value)


def test_request_and_response_size_bounds() -> None:
    adapter, _transport = client([response(valid_payload())], max_request_bytes=10)
    with pytest.raises(ProviderRequestTooLargeError):
        adapter.complete(LLMRequest(prompt="large prompt", model="model"))
    adapter, _transport = client(
        [HTTPResponse(200, {}, b"x" * 11)], max_response_bytes=10
    )
    with pytest.raises(ProviderResponseTooLargeError):
        adapter.complete(LLMRequest(prompt="prompt", model="model"))


@pytest.mark.parametrize(
    "url",
    [
        "https://user:pass@example.com/v1",
        "https://example.com/v1?token=abc",
        "file:///tmp/api",
        "ftp://provider.example/v1",
    ],
)
def test_unsafe_urls_are_rejected(url: str) -> None:
    with pytest.raises(ProviderConfigurationError):
        OpenAICompatibleConfig(base_url=url)


def test_remote_http_requires_explicit_opt_in() -> None:
    with pytest.raises(ProviderConfigurationError):
        OpenAICompatibleConfig(base_url="http://provider.example/v1")
    assert OpenAICompatibleConfig(
        base_url="http://provider.example/v1", allow_insecure_http=True
    ).endpoint.endswith("/chat/completions")
