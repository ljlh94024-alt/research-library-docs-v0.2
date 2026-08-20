"""Source-controlled prompt registry."""

from __future__ import annotations

from dataclasses import dataclass
from string import Formatter


@dataclass(frozen=True, slots=True)
class PromptSpec:
    prompt_id: str
    version: str
    task_type: str
    model_role: str
    schema_id: str
    schema_version: str
    system_template: str
    user_template: str
    required_variables: tuple[str, ...]

    def render(self, variables: dict[str, object]) -> tuple[str, str]:
        missing = set(self.required_variables) - variables.keys()
        if missing:
            raise KeyError(f"missing prompt variables: {', '.join(sorted(missing))}")
        names = {
            field_name
            for _, field_name, _, _ in Formatter().parse(self.user_template)
            if field_name
        }
        names |= {
            field_name
            for _, field_name, _, _ in Formatter().parse(self.system_template)
            if field_name
        }
        missing = names - variables.keys()
        if missing:
            raise KeyError(f"missing prompt variables: {', '.join(sorted(missing))}")
        try:
            return self.system_template.format(**variables), self.user_template.format(**variables)
        except KeyError as exc:
            raise KeyError(f"missing prompt variable: {exc.args[0]}") from exc


class PromptRegistry:
    def __init__(self, specs: tuple[PromptSpec, ...] = ()) -> None:
        self._specs: dict[tuple[str, str], PromptSpec] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: PromptSpec) -> PromptSpec:
        key = (spec.prompt_id, spec.version)
        if key in self._specs:
            raise ValueError(f"duplicate prompt registration: {key}")
        self._specs[key] = spec
        return spec

    def get(self, prompt_id: str, version: str) -> PromptSpec:
        try:
            return self._specs[(prompt_id, version)]
        except KeyError as exc:
            raise KeyError(f"unknown prompt: {prompt_id}/{version}") from exc

    lookup = get


def default_prompt_registry() -> PromptRegistry:
    system = "Return only strict JSON matching schema {schema_id} version {schema_version}."
    return PromptRegistry(
        tuple(
            PromptSpec(
                prompt_id=prompt_id,
                version="v1",
                task_type=task_type,
                model_role=role,
                schema_id=schema_id,
                schema_version="1",
                system_template=system,
                user_template=user,
                required_variables=variables,
            )
            for prompt_id, task_type, role, schema_id, user, variables in (
                (
                    "semantic.evidence_extract",
                    "evidence_extract",
                    "extractor",
                    "semantic.evidence-extraction",
                    "Snapshots: {snapshots}",
                    ("snapshots", "schema_id", "schema_version"),
                ),
                (
                    "semantic.claim_extract",
                    "claim_extract",
                    "extractor",
                    "semantic.claim-extraction",
                    "Evidence: {evidences}",
                    ("evidences", "schema_id", "schema_version"),
                ),
                (
                    "semantic.evidence_link",
                    "evidence_link",
                    "fast",
                    "semantic.evidence-relation",
                    "Evidence: {evidences}\nClaims: {claims}",
                    ("evidences", "claims", "schema_id", "schema_version"),
                ),
                (
                    "semantic.source_dependency",
                    "source_dependency",
                    "fast",
                    "semantic.source-dependency",
                    "Sources: {sources}",
                    ("sources", "schema_id", "schema_version"),
                ),
                (
                    "semantic.independence",
                    "independence",
                    "fast",
                    "semantic.source-dependency",
                    "Sources: {sources}",
                    ("sources", "schema_id", "schema_version"),
                ),
            )
        )
    )


__all__ = ["PromptRegistry", "PromptSpec", "default_prompt_registry"]
