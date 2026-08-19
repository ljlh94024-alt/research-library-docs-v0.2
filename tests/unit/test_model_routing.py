import pytest

from research_library.llm import (
    FakeLLMClient,
    LLMClientRegistry,
    ModelRole,
    StaticModelRouter,
)


def test_static_router_uses_frozen_phase1c_roles() -> None:
    router = StaticModelRouter()
    assert router.route("evidence_extract").role is ModelRole.EXTRACTOR
    assert router.route("claim_extract").role is ModelRole.EXTRACTOR
    assert router.route("evidence_link").role is ModelRole.FAST
    assert router.route("source_dependency").role is ModelRole.FAST
    with pytest.raises(KeyError, match="unknown"):
        router.route("resolve")


def test_client_registry_rejects_duplicate_and_unknown_provider() -> None:
    registry = LLMClientRegistry()
    client = FakeLLMClient()
    registry.register("fake", client)
    assert registry.get("fake") is client
    with pytest.raises(ValueError, match="duplicate"):
        registry.register("fake", client)
    with pytest.raises(KeyError, match="unknown"):
        registry.get("real")
