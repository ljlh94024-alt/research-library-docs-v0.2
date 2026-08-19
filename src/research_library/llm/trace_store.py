"""Content-addressed canonical JSON traces for structured LLM calls."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class LLMTraceIntegrityError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class TraceRef:
    ref: str
    content_hash: str


class LLMTraceStore:
    def __init__(self, root: str | Path = "data/llm-traces") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _hash(payload: dict[str, Any]) -> str:
        return hashlib.sha256(_canonical(payload)).hexdigest()

    def write(self, kind: str, payload: dict[str, Any]) -> TraceRef:
        content_hash = self._hash(payload)
        ref = f"llm-trace:{content_hash}"
        envelope = {"content_hash": content_hash, "kind": kind, "payload": payload, "ref": ref}
        path = self.root / f"{content_hash}.json"
        encoded = _canonical(envelope)
        if path.exists() and path.read_bytes() != encoded:
            raise LLMTraceIntegrityError(f"trace address already contains different bytes: {ref}")
        path.write_bytes(encoded)
        return TraceRef(ref, content_hash)

    def _path_for_ref(self, ref: str) -> Path:
        match = re.fullmatch(r"llm-trace:([0-9a-f]{64})", ref)
        if match is None:
            raise LLMTraceIntegrityError("unsafe trace ref")
        return self.root / f"{match.group(1)}.json"

    def read(self, ref: str) -> dict[str, Any]:
        path = self._path_for_ref(ref)
        if not path.exists():
            raise LLMTraceIntegrityError(f"missing trace: {ref}")
        raw = path.read_bytes()
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LLMTraceIntegrityError("trace is not valid UTF-8 JSON") from exc
        if not isinstance(value, dict) or value.get("ref") != ref:
            raise LLMTraceIntegrityError("trace does not match requested address")
        payload = value.get("payload")
        if not isinstance(payload, dict) or value.get("content_hash") != self._hash(payload):
            raise LLMTraceIntegrityError("trace content hash mismatch")
        if raw != _canonical(value):
            raise LLMTraceIntegrityError("trace bytes are not canonical JSON")
        return payload

    def verify(self, ref: str, content_hash: str) -> dict[str, Any]:
        if ref != f"llm-trace:{content_hash}":
            raise LLMTraceIntegrityError("trace ref/hash mismatch")
        return self.read(ref)


__all__ = ["LLMTraceIntegrityError", "LLMTraceStore", "TraceRef"]
