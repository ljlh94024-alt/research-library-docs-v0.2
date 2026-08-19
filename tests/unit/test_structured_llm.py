import json

import pytest

from research_library.llm import (
    FakeLLMClient,
    LLMClientRegistry,
    LLMRetryExhaustedError,
    LLMTraceStore,
    ScriptedFakeLLMClient,
    StructuredLLMRuntime,
)
from research_library.llm.structured import (
    ClaimExtractionOutput,
    EvidenceExtractionOutput,
)


def _runtime(client, tmp_path):
    clients = LLMClientRegistry()
    clients.register("fake", client)
    return StructuredLLMRuntime(clients=clients, trace_store=LLMTraceStore(tmp_path))


def test_strict_schema_rejects_extra_fields_and_accepts_valid_json(tmp_path) -> None:
    runtime = _runtime(
        FakeLLMClient(default_response=json.dumps({"items": [{"text": "evidence"}]})), tmp_path
    )
    output = runtime.invoke(
        stage_run_id="stage-1",
        task_type="evidence_extract",
        prompt_id="semantic.evidence_extract",
        prompt_version="v1",
        schema=EvidenceExtractionOutput,
        variables={"snapshots": []},
    )
    assert output.items[0].text == "evidence"
    assert runtime.records[0].attempt == 1
    strict = _runtime(
        ScriptedFakeLLMClient([json.dumps({"items": [{"text": "ok", "unknown": True}]})]),
        tmp_path / "strict",
    )
    with pytest.raises(LLMRetryExhaustedError):
        strict.invoke(
            stage_run_id="stage-2",
            task_type="evidence_extract",
            prompt_id="semantic.evidence_extract",
            prompt_version="v1",
            schema=EvidenceExtractionOutput,
            variables={"snapshots": []},
        )
    assert len(strict.records) == 2


def test_retry_preserves_failed_attempt_then_succeeds(tmp_path) -> None:
    runtime = _runtime(
        ScriptedFakeLLMClient(
            [
                "not-json",
                json.dumps({"items": [{"text": "recovered"}]}),
            ]
        ),
        tmp_path,
    )
    output = runtime.invoke(
        stage_run_id="stage-retry",
        task_type="evidence_extract",
        prompt_id="semantic.evidence_extract",
        prompt_version="v1",
        schema=EvidenceExtractionOutput,
        variables={"snapshots": []},
        logical_request_id="logical-retry",
    )
    assert output.items[0].text == "recovered"
    assert [item.attempt for item in runtime.records] == [1, 2]
    assert {item.logical_request_id for item in runtime.records} == {"logical-retry"}
    assert runtime.records[0].status.value == "failed"
    assert runtime.records[1].status.value == "succeeded"


def test_reference_validation_and_exhaustion_do_not_fallback(tmp_path) -> None:
    runtime = _runtime(
        ScriptedFakeLLMClient(
            [
                json.dumps(
                    {
                        "items": [
                            {
                                "statement": "claim",
                                "extraction_confidence": 0.5,
                                "evidence_candidate_ids": ["unknown"],
                            }
                        ]
                    }
                ),
                json.dumps(
                    {
                        "items": [
                            {
                                "statement": "claim",
                                "extraction_confidence": 0.5,
                                "evidence_candidate_ids": ["unknown"],
                            }
                        ]
                    }
                ),
            ]
        ),
        tmp_path,
    )
    with pytest.raises(LLMRetryExhaustedError):
        runtime.invoke(
            stage_run_id="stage-invalid-ref",
            task_type="claim_extract",
            prompt_id="semantic.claim_extract",
            prompt_version="v1",
            schema=ClaimExtractionOutput,
            variables={"evidences": [], "evidence_candidate_ids": ["known"]},
        )
    assert all(item.error_type == "StructuredOutputError" for item in runtime.records)
    assert all(item.response_ref for item in runtime.records)
