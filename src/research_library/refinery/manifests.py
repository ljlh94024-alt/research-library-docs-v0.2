"""Canonical, persistent content-addressed manifests for refinery stages."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any


class ManifestIntegrityError(RuntimeError):
    """Raised when a manifest is missing, unsafe, or has been tampered with."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_artifact_id(kind: str, *parts: object) -> str:
    """Create a stable namespaced ID from canonical JSON input parts."""

    payload = canonical_json([kind, *(str(part) for part in parts)])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f"{kind}-{digest}"


@dataclass(frozen=True, slots=True)
class StageManifest:
    stage_name: str
    stage_version: str
    input_artifact_ids: tuple[str, ...] = ()
    output_artifact_ids: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.stage_name.strip() or not self.stage_version.strip():
            raise ValueError("stage_name and stage_version must be non-empty")
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

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> StageManifest:
        manifest = cls(
            stage_name=str(value["stage_name"]),
            stage_version=str(value["stage_version"]),
            input_artifact_ids=tuple(value.get("input_artifact_ids", ())),
            output_artifact_ids=tuple(value.get("output_artifact_ids", ())),
            metadata=dict(value.get("metadata", {})),
        )
        if value.get("manifest_id") != manifest.manifest_id:
            raise ManifestIntegrityError("manifest ID does not match canonical payload")
        if value.get("content_hash") != manifest.content_hash:
            raise ManifestIntegrityError("manifest content hash does not match payload")
        return manifest


class StageManifestStore:
    """Filesystem store whose safe refs can be dereferenced after process exit."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path_for_ref(self, ref: str) -> Path:
        if not isinstance(ref, str) or not ref.startswith("manifest:"):
            raise ManifestIntegrityError("manifest ref must use manifest:<id> form")
        manifest_id = ref.removeprefix("manifest:")
        path_part = PurePosixPath(manifest_id)
        if (
            not manifest_id
            or path_part.is_absolute()
            or ".." in path_part.parts
            or path_part.name != manifest_id
            or not manifest_id.startswith("manifest-")
            or len(manifest_id) != len("manifest-") + 64
        ):
            raise ManifestIntegrityError("manifest ref is not a safe content address")
        return self.root / f"{manifest_id}.json"

    def write(self, manifest: StageManifest) -> str:
        path = self._path_for_ref(manifest.ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = (canonical_json(manifest.as_dict()) + "\n").encode("utf-8")
        if path.exists():
            if path.read_bytes() != data:
                raise ManifestIntegrityError(f"existing manifest differs: {manifest.ref}")
            return manifest.ref
        try:
            with path.open("xb") as handle:
                handle.write(data)
        except FileExistsError:
            if path.read_bytes() != data:
                raise ManifestIntegrityError(f"existing manifest differs: {manifest.ref}")
        return manifest.ref

    def read(self, ref: str) -> StageManifest:
        path = self._path_for_ref(ref)
        try:
            raw = path.read_bytes()
        except FileNotFoundError as exc:
            raise ManifestIntegrityError(f"manifest is missing: {ref}") from exc
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ManifestIntegrityError(f"manifest is not canonical JSON: {ref}") from exc
        return StageManifest.from_dict(value)

    def verify(self, ref: str) -> bool:
        self.read(ref)
        return True


def manifest_artifact_ids(manifest: StageManifest) -> Sequence[str]:
    return manifest.output_artifact_ids


__all__ = [
    "ManifestIntegrityError",
    "StageManifest",
    "StageManifestStore",
    "canonical_json",
    "manifest_artifact_ids",
    "stable_artifact_id",
]
