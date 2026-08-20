"""Validated configuration for an OpenAI-compatible chat endpoint."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit

from pydantic import SecretStr

from .errors import ProviderConfigurationError


def _is_loopback(hostname: str) -> bool:
    normalized = hostname.strip("[]").casefold()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class OpenAICompatibleConfig:
    provider_name: str = "openai_compatible"
    base_url: str = "https://api.openai.com/v1"
    api_key: SecretStr | None = None
    timeout_seconds: float = 30.0
    include_response_format: bool = True
    allow_insecure_http: bool = False
    max_request_bytes: int = 8 * 1024 * 1024
    max_response_bytes: int = 4 * 1024 * 1024

    def __post_init__(self) -> None:
        if not self.provider_name.strip():
            raise ProviderConfigurationError("provider_name must be non-empty")
        parts = urlsplit(self.base_url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ProviderConfigurationError("base_url must be an absolute http(s) URL")
        if parts.username is not None or parts.password is not None:
            raise ProviderConfigurationError("base_url must not contain URL userinfo")
        if parts.query or parts.fragment:
            raise ProviderConfigurationError("base_url must not contain query or fragment")
        if (
            parts.scheme == "http"
            and not _is_loopback(parts.hostname)
            and not self.allow_insecure_http
        ):
            raise ProviderConfigurationError(
                "remote HTTP is disabled; use HTTPS or opt in explicitly"
            )
        if self.timeout_seconds <= 0:
            raise ProviderConfigurationError("timeout_seconds must be positive")
        for value, name in (
            (self.max_request_bytes, "max_request_bytes"),
            (self.max_response_bytes, "max_response_bytes"),
        ):
            if isinstance(value, bool) or value < 1:
                raise ProviderConfigurationError(f"{name} must be positive")
        if isinstance(self.api_key, str):
            object.__setattr__(self, "api_key", SecretStr(self.api_key) if self.api_key else None)

    @property
    def api_key_value(self) -> str | None:
        return self.api_key.get_secret_value() if self.api_key is not None else None

    @property
    def endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"


__all__ = ["OpenAICompatibleConfig"]
