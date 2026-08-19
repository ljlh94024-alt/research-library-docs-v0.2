import json

import pytest

from research_library.llm import LLMTraceIntegrityError, LLMTraceStore


def test_trace_store_roundtrip_and_canonical_integrity(tmp_path) -> None:
    store = LLMTraceStore(tmp_path)
    reference = store.write("request", {"prompt": "hello", "model": "fake"})
    assert store.read(reference.ref) == {"prompt": "hello", "model": "fake"}
    path = tmp_path / f"{reference.content_hash}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["payload"] = {"prompt": "different"}
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(LLMTraceIntegrityError):
        store.read(reference.ref)


def test_trace_store_rejects_coherent_swap_and_missing_or_unsafe_refs(tmp_path) -> None:
    store = LLMTraceStore(tmp_path)
    first = store.write("request", {"prompt": "first"})
    second = store.write("request", {"prompt": "second"})
    first_path = tmp_path / f"{first.content_hash}.json"
    second_path = tmp_path / f"{second.content_hash}.json"
    first_path.write_bytes(second_path.read_bytes())
    with pytest.raises(LLMTraceIntegrityError, match="requested address"):
        store.read(first.ref)
    with pytest.raises(LLMTraceIntegrityError, match="unsafe"):
        store.read("../secret")
    with pytest.raises(LLMTraceIntegrityError, match="missing"):
        store.read("llm-trace:" + "0" * 64)
