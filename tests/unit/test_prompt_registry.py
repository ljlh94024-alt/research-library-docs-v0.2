import pytest

from research_library.llm import PromptRegistry, PromptSpec, default_prompt_registry


def test_default_registry_contains_versioned_phase1c_prompts() -> None:
    registry = default_prompt_registry()
    assert (
        registry.get("semantic.evidence_extract", "v1").schema_id == "semantic.evidence-extraction"
    )
    assert registry.get("semantic.source_dependency", "v1").model_role == "fast"


def test_prompt_registry_rejects_duplicates_and_missing_values() -> None:
    spec = PromptSpec("p", "v1", "task", "fast", "schema", "1", "{x}", "{x}", ("x",))
    registry = PromptRegistry((spec,))
    with pytest.raises(ValueError, match="duplicate"):
        registry.register(spec)
    with pytest.raises(KeyError, match="unknown prompt"):
        registry.get("missing", "v1")
    with pytest.raises(KeyError, match="missing"):
        spec.render({})
