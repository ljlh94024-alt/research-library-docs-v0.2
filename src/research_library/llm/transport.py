"""Small injectable HTTP transport boundary with no retry or redirect behavior."""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class HTTPRequest:
    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes
    timeout_seconds: float


@dataclass(frozen=True, slots=True)
class HTTPResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


class HTTPTransport(Protocol):
    def send(self, request: HTTPRequest) -> HTTPResponse: ...


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def http_error_301(self, req, fp, code, msg, headers):  # type: ignore[no-untyped-def]
        return fp

    http_error_302 = http_error_301
    http_error_303 = http_error_301
    http_error_307 = http_error_301
    http_error_308 = http_error_301


class UrllibHTTPTransport:
    """Production stdlib transport. It performs exactly one request."""

    def __init__(self, *, max_response_bytes: int = 4 * 1024 * 1024) -> None:
        if max_response_bytes < 1:
            raise ValueError("max_response_bytes must be positive")
        self.max_response_bytes = max_response_bytes
        self._opener = urllib.request.build_opener(_NoRedirectHandler())

    def send(self, request: HTTPRequest) -> HTTPResponse:
        encoded = urllib.request.Request(
            request.url,
            data=request.body,
            headers=dict(request.headers),
            method=request.method,
        )
        try:
            response = self._opener.open(encoded, timeout=request.timeout_seconds)
        except urllib.error.HTTPError as exc:
            response = exc
        try:
            body = response.read(self.max_response_bytes + 1)
            return HTTPResponse(
                status_code=int(response.status),
                headers=dict(response.headers.items()),
                body=body,
            )
        finally:
            response.close()


class ScriptedHTTPTransport:
    """Deterministic test transport; it never accesses the network."""

    def __init__(self, script: Sequence[HTTPResponse | BaseException]) -> None:
        self._script = list(script)
        self.requests: list[HTTPRequest] = []

    @property
    def send_count(self) -> int:
        return len(self.requests)

    def send(self, request: HTTPRequest) -> HTTPResponse:
        self.requests.append(request)
        if not self._script:
            raise RuntimeError("scripted HTTP response sequence exhausted")
        value = self._script.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


__all__ = [
    "HTTPRequest",
    "HTTPResponse",
    "HTTPTransport",
    "ScriptedHTTPTransport",
    "UrllibHTTPTransport",
]
