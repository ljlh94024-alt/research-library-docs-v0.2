"""Content-addressed manifests for deterministic refinery stage outputs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_artifact_id(kind: str, *parts: object) -> str:
    """Return a stable, namespaced identifier without using runtime randomness."""

    payload = canonical_json([kind, *(str(part) for part in parts)])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f"{kind}-{digest}"


@dataclass(frozen=True, slots=True)
class StageManifest:
    """A deterministic description of one stage's inputs and outputs."""

    stage_name: str
    stage_version: str
    input_artifact_ids: tuple[str, ...] = ()
    output_artifact_ids: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.stage_name.strip():
            raise ValueError("stage_name must be non-empty")
        if not self.stage_version.strip():
            raise ValueError("stage_version must be non-empty")
        object.__setattr__(self, "input_artifact_ids", tuple(self.input_artifact_ids))
        object.__setattr__(self, "output_artifact_ids", tuple(self.output_artifact_ids))
        object.__setattr__(self, "metadata", dict(self.metadata))
        for name, values in (
            ("input_artifact_ids", self.input_artifact_ids),
            ("output_artifact_ids", self.output_artifact_ids),
        ):
            if any(not isinstance(item, str) or not item.strip() for item in values):
                raise ValueError(f"{name} must contain only non-empty IDs")

    @property
    def payload(self) -> dict[str, object]:
        return {
            "stage_name": self.stage_name,
            "stage_version": self.stage_version,
            "input_artifact_ids": self.input_artifact_ids,
            "output_artifact_ids": self.output_artifact_ids,
            "metadata": self.metadata,
        }

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(canonical_json(self.payload).encode("utf-8")).hexdigest()

    @property
    def manifest_id(self) -> str:
        return f"manifest-{self.content_hash}"

    @property
    def ref(self) -> str:
        return f"manifest:{self.manifest_id}"

    def as_dict(self) -> dict[str, object]:
        return {**self.payload, "manifest_id": self.manifest_id, "content_hash": self.content_hash}


def manifest_artifact_ids(manifest: StageManifest) -> Sequence[str]:
    """Expose output IDs through a small stable helper for callers and tests."""

    return manifest.output_artifact_ids
