"""OpenAI-compatible ``/chat/completions`` adapter without SDK dependencies."""

from __future__ import annotations

import json
import socket
import urllib.error
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from .client import LLMRequest, LLMResponse
from .errors import (
    LLMProviderError,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderContentFilterError,
    ProviderHTTPError,
    ProviderPermissionError,
    ProviderProtocolError,
    ProviderRateLimitError,
    ProviderRedirectError,
    ProviderRequestTooLargeError,
    ProviderResponseTooLargeError,
    ProviderTimeoutError,
    ProviderTruncatedResponseError,
    redact_secrets,
    safe_metadata,
)
from .provider_config import OpenAICompatibleConfig
from .transport import HTTPRequest, HTTPResponse, HTTPTransport, UrllibHTTPTransport

_RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


def _header(headers: Mapping[str, str], name: str) -> str | None:
    wanted = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == wanted:
            return str(value)
    return None


def _error_fields(body: bytes) -> tuple[str, str | None, str | None]:
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "provider returned an HTTP error", None, None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("error"), dict):
        return "provider returned an HTTP error", None, None
    error = parsed["error"]
    message = redact_secrets(error.get("message", "provider returned an HTTP error"))
    error_type = error.get("type") if isinstance(error.get("type"), str) else None
    code = error.get("code") if isinstance(error.get("code"), str) else None
    return message[:500], error_type, code


def _retry_after(headers: Mapping[str, str]) -> float | None:
    value = _header(headers, "Retry-After")
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return seconds if seconds >= 0 else None


def _status_error(response: HTTPResponse, endpoint_path: str) -> LLMProviderError:
    status = response.status_code
    if 300 <= status < 400:
        return ProviderRedirectError(status)
    message, error_type, error_code = _error_fields(response.body)
    metadata = safe_metadata(
        {
            "http_status": status,
            "retryable": status in _RETRYABLE_STATUS_CODES or status >= 500,
            "provider_error_type": error_type,
            "provider_error_code": error_code,
            "retry_after_seconds": _retry_after(response.headers),
            "endpoint_path": endpoint_path,
        }
    )
    if status == 401:
        return ProviderAuthenticationError(
            message,
            status_code=status,
            provider_error_code=error_code,
            metadata=metadata,
        )
    if status == 403:
        return ProviderPermissionError(
            message,
            status_code=status,
            provider_error_code=error_code,
            metadata=metadata,
        )
    if status == 429:
        return ProviderRateLimitError(
            message,
            status_code=status,
            provider_error_code=error_code,
            metadata=metadata,
        )
    return ProviderHTTPError(
        message,
        retryable=status in _RETRYABLE_STATUS_CODES or status >= 500,
        status_code=status,
        provider_error_code=error_code,
        metadata=metadata,
    )


def _transport_error(exc: BaseException) -> LLMProviderError:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return ProviderTimeoutError(type(exc).__name__)
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return ProviderTimeoutError(type(reason).__name__)
        return ProviderConnectionError(type(reason).__name__)
    if isinstance(exc, (ConnectionError, OSError)):
        return ProviderConnectionError(type(exc).__name__)
    return ProviderConnectionError(type(exc).__name__)


class OpenAICompatibleClient:
    """One ``complete`` call issues one physical HTTP request, never retries."""

    def __init__(
        self,
        config: OpenAICompatibleConfig,
        *,
        transport: HTTPTransport | None = None,
    ) -> None:
        self.config = config
        self.transport = transport or UrllibHTTPTransport(
            max_response_bytes=config.max_response_bytes
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        if not request.model or not request.model.strip():
            raise ProviderProtocolError(
                "OpenAI-compatible requests require a non-empty model", retryable=False
            )
        messages: list[dict[str, str]] = []
        if request.system_prompt is not None:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
        }
        if self.config.include_response_format:
            payload["response_format"] = {"type": "json_object"}
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(body) > self.config.max_request_bytes:
            raise ProviderRequestTooLargeError(len(body), self.config.max_request_bytes)
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.config.api_key_value is not None:
            headers["Authorization"] = f"Bearer {self.config.api_key_value}"
        http_request = HTTPRequest(
            method="POST",
            url=self.config.endpoint,
            headers=headers,
            body=body,
            timeout_seconds=self.config.timeout_seconds,
        )
        try:
            response = self.transport.send(http_request)
        except LLMProviderError:
            raise
        except BaseException as exc:
            raise _transport_error(exc) from exc
        if len(response.body) > self.config.max_response_bytes:
            raise ProviderResponseTooLargeError(self.config.max_response_bytes)
        if not 200 <= response.status_code < 300:
            raise _status_error(response, urlsplit(self.config.endpoint).path)
        return self._parse_response(response, request)

    def _parse_response(self, response: HTTPResponse, request: LLMRequest) -> LLMResponse:
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderProtocolError("provider response is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ProviderProtocolError("provider response must be a JSON object")
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderProtocolError("provider response choices must be a non-empty list")
        choice = choices[0]
        if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
            raise ProviderProtocolError("provider response choice message is missing")
        message = choice["message"]
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderProtocolError(
                "provider response message content must be a non-empty string"
            )
        finish_reason = choice.get("finish_reason")
        if finish_reason == "length":
            raise ProviderTruncatedResponseError(finish_reason)
        if finish_reason == "content_filter":
            raise ProviderContentFilterError()
        usage = self._normalize_usage(payload.get("usage"))
        response_id = payload.get("id") if isinstance(payload.get("id"), str) else None
        provider_request_id = _header(response.headers, "x-request-id")
        raw = {
            "request_id": response_id,
            "http_status": response.status_code,
            "finish_reason": finish_reason,
            "provider_request_id_header": provider_request_id,
        }
        return LLMResponse(
            text=content,
            model=payload.get("model") if isinstance(payload.get("model"), str) else request.model,
            provider=self.config.provider_name,
            raw={key: value for key, value in raw.items() if value is not None},
            usage=usage,
        )

    @staticmethod
    def _normalize_usage(value: object) -> dict[str, int]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ProviderProtocolError("provider usage must be an object")
        result: dict[str, int] = {}
        for source, target in (
            ("prompt_tokens", "input_tokens"),
            ("completion_tokens", "output_tokens"),
            ("total_tokens", "total_tokens"),
        ):
            item = value.get(source)
            if item is None:
                continue
            if isinstance(item, bool) or not isinstance(item, int) or item < 0:
                raise ProviderProtocolError(
                    f"provider usage field {source} must be a non-negative integer"
                )
            result[target] = item
        return result


__all__ = ["OpenAICompatibleClient"]
