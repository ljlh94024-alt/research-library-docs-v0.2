"""Safe, typed errors for OpenAI-compatible provider calls."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)((?:api[_-]?key|apikey|token|secret|credential)\s*[=:]\s*)[^\s,;]+"),
)


def redact_secrets(value: object) -> str:
    """Return a bounded string with common credential forms removed."""

    text = str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(r"\1[REDACTED]", text)
    return text[:2000]


def safe_metadata(metadata: Mapping[str, Any] | None = None, **values: Any) -> dict[str, Any]:
    """Keep provider telemetry small, typed, and free of credential-shaped keys."""

    combined = {**dict(metadata or {}), **values}
    result: dict[str, Any] = {}
    forbidden = {"authorization", "api_key", "apikey", "cookie", "credential", "secret"}
    for key, value in combined.items():
        key_text = str(key)
        if any(part in key_text.casefold() for part in forbidden):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            result[key_text] = redact_secrets(value) if isinstance(value, str) else value
    return result


class LLMProviderError(RuntimeError):
    """Base provider error; retry ownership remains with StructuredLLMRuntime."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        status_code: int | None = None,
        provider_error_code: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.retryable = retryable
        self.status_code = status_code
        self.provider_error_code = provider_error_code
        self.audit_metadata = safe_metadata(
            metadata,
            http_status=status_code,
            retryable=retryable,
            provider_error_code=provider_error_code,
        )
        super().__init__(redact_secrets(message))


class ProviderConfigurationError(LLMProviderError):
    def __init__(self, message: str) -> None:
        super().__init__(message, retryable=False)


class ProviderAuthenticationError(LLMProviderError):
    def __init__(self, message: str = "provider authentication failed", **kwargs: Any) -> None:
        super().__init__(message, retryable=False, **kwargs)


class ProviderPermissionError(LLMProviderError):
    def __init__(self, message: str = "provider permission denied", **kwargs: Any) -> None:
        super().__init__(message, retryable=False, **kwargs)


class ProviderRateLimitError(LLMProviderError):
    def __init__(self, message: str = "provider rate limit", **kwargs: Any) -> None:
        super().__init__(message, retryable=True, **kwargs)


class ProviderTimeoutError(LLMProviderError):
    def __init__(self, message: str = "provider request timed out", **kwargs: Any) -> None:
        super().__init__(message, retryable=True, **kwargs)


class ProviderConnectionError(LLMProviderError):
    def __init__(self, message: str = "provider connection failed", **kwargs: Any) -> None:
        super().__init__(message, retryable=True, **kwargs)


class ProviderHTTPError(LLMProviderError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        status_code: int,
        provider_error_code: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            retryable=retryable,
            status_code=status_code,
            provider_error_code=provider_error_code,
            metadata=metadata,
        )


class ProviderRedirectError(ProviderHTTPError):
    def __init__(self, status_code: int) -> None:
        super().__init__(
            f"provider redirect refused (HTTP {status_code})",
            retryable=False,
            status_code=status_code,
        )


class ProviderProtocolError(LLMProviderError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = True,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, retryable=retryable, metadata=metadata)


class ProviderRequestTooLargeError(LLMProviderError):
    def __init__(self, size: int, limit: int) -> None:
        super().__init__(
            f"provider request body exceeds {limit} bytes (got {size})", retryable=False
        )


class ProviderResponseTooLargeError(LLMProviderError):
    def __init__(self, limit: int) -> None:
        super().__init__(f"provider response exceeds {limit} bytes", retryable=False)


class ProviderTruncatedResponseError(LLMProviderError):
    def __init__(self, finish_reason: str) -> None:
        super().__init__(f"provider response was truncated ({finish_reason})", retryable=False)


class ProviderContentFilterError(LLMProviderError):
    def __init__(self) -> None:
        super().__init__("provider refused content", retryable=False)


__all__ = [
    "LLMProviderError",
    "ProviderAuthenticationError",
    "ProviderConfigurationError",
    "ProviderConnectionError",
    "ProviderContentFilterError",
    "ProviderHTTPError",
    "ProviderPermissionError",
    "ProviderProtocolError",
    "ProviderRateLimitError",
    "ProviderRedirectError",
    "ProviderRequestTooLargeError",
    "ProviderResponseTooLargeError",
    "ProviderTimeoutError",
    "ProviderTruncatedResponseError",
    "redact_secrets",
    "safe_metadata",
]
