import json

import pytest

from research_library.llm import (
    HTTPResponse,
    LLMClientRegistry,
    LLMTraceStore,
    ModelRole,
    ModelTarget,
    OpenAICompatibleClient,
    OpenAICompatibleConfig,
    ProviderAuthenticationError,
    ScriptedHTTPTransport,
    StaticModelRouter,
    StructuredLLMRuntime,
)
from research_library.llm.structured import ClaimOutputItem
from research_library.refinery import (
    DeterministicRefinery,
    FixtureHarness,
    FixtureSemanticBackend,
    StructuredLLMSemanticBackend,
    get_golden_fixture,
    stable_artifact_id,
)
from research_library.storage import SQLiteRepository

SECRET = "SUPER_SECRET_PHASE1D_TEST_KEY_987654321"


def envelope(content: str, *, status: int = 200) -> HTTPResponse:
    return HTTPResponse(
        status,
        {},
        json.dumps(
            {
                "id": "request-123",
                "model": "provider-model",
                "choices": [
                    {"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        ).encode(),
    )


def error(status: int) -> HTTPResponse:
    return HTTPResponse(
        status,
        {"Retry-After": "1"},
        json.dumps({"error": {"message": "rate limit", "code": "rate_limit"}}).encode(),
    )


def runtime_for(transport: ScriptedHTTPTransport, trace_root, *, max_attempts: int = 2):
    config = OpenAICompatibleConfig(
        base_url="http://127.0.0.1:1234/v1",
        api_key=SECRET,
    )
    client = OpenAICompatibleClient(config, transport=transport)
    clients = LLMClientRegistry()
    clients.register("openai_compatible", client)
    router = StaticModelRouter(
        {
            task: ModelTarget(
                ModelRole.EXTRACTOR if task != "independence" else ModelRole.FAST,
                "openai_compatible",
                "provider-model",
            )
            for task in ("evidence_extract", "claim_extract", "evidence_link", "independence")
        }
    )
    return StructuredLLMRuntime(
        clients=clients,
        router=router,
        trace_store=LLMTraceStore(trace_root),
        max_attempts=max_attempts,
    )


def invoke(runtime: StructuredLLMRuntime):
    from research_library.llm import EvidenceExtractionOutput

    return runtime.invoke(
        stage_run_id="stage-provider",
        task_type="evidence_extract",
        prompt_id="semantic.evidence_extract",
        prompt_version="v1",
        schema=EvidenceExtractionOutput,
        variables={"snapshots": [{"snapshot_id": "snapshot-1", "content": "synthetic"}]},
        logical_request_id="logical-provider-request",
    )


def test_429_then_success_is_two_physical_attempts_and_two_audit_records(tmp_path) -> None:
    transport = ScriptedHTTPTransport([error(429), envelope('{"items": []}')])
    runtime = runtime_for(transport, tmp_path / "traces")
    result = invoke(runtime)
    assert result.items == []
    assert transport.send_count == 2
    assert [record.attempt for record in runtime.records] == [1, 2]
    assert [record.status.value for record in runtime.records] == ["failed", "succeeded"]
    assert all(
        record.logical_request_id == "logical-provider-request" for record in runtime.records
    )
    assert runtime.records[0].metadata["http_status"] == 429
    assert runtime.records[0].metadata["retryable"] is True
    assert runtime.records[1].metadata["http_status"] == 200


def test_401_is_one_call_and_does_not_consume_second_scripted_response(tmp_path) -> None:
    transport = ScriptedHTTPTransport([error(401), envelope('{"items": []}')])
    runtime = runtime_for(transport, tmp_path / "traces")
    with pytest.raises(ProviderAuthenticationError):
        invoke(runtime)
    assert transport.send_count == 1
    assert len(runtime.records) == 1
    assert runtime.records[0].status.value == "failed"
    assert runtime.records[0].attempt == 1


def test_timeout_then_success_is_runtime_owned_retry(tmp_path) -> None:
    transport = ScriptedHTTPTransport([TimeoutError("timed out"), envelope('{"items": []}')])
    runtime = runtime_for(transport, tmp_path / "traces")
    invoke(runtime)
    assert transport.send_count == 2
    assert [record.status.value for record in runtime.records] == ["failed", "succeeded"]
    assert runtime.records[0].metadata["retryable"] is True


def test_valid_provider_envelope_but_invalid_semantic_json_retries_in_runtime(tmp_path) -> None:
    transport = ScriptedHTTPTransport([envelope("not JSON"), envelope('{"items": []}')])
    runtime = runtime_for(transport, tmp_path / "traces")
    invoke(runtime)
    assert transport.send_count == 2
    assert [record.status.value for record in runtime.records] == ["failed", "succeeded"]


def test_secret_only_appears_in_outbound_header_and_not_trace_or_audit(tmp_path) -> None:
    transport = ScriptedHTTPTransport([envelope('{"items": []}')])
    runtime = runtime_for(transport, tmp_path / "traces")
    invoke(runtime)
    assert SECRET in transport.requests[0].headers["Authorization"]
    trace_bytes = b"".join(path.read_bytes() for path in (tmp_path / "traces").glob("*.json"))
    assert SECRET.encode() not in trace_bytes
    assert all(SECRET not in repr(record) for record in runtime.records)


def _provider_envelope(content: object) -> HTTPResponse:
    return HTTPResponse(
        200,
        {},
        json.dumps(
            {
                "id": "provider-e2e-request",
                "model": "provider-model",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": json.dumps(content)},
                        "finish_reason": "stop",
                    }
                ],
            }
        ).encode(),
    )


def _semantic_provider_script(fixture_id: str, backend: FixtureSemanticBackend, prepared):
    fixture = get_golden_fixture(fixture_id)
    snapshot_ids = {
        item.key: backend.snapshot_id(fixture_id, item) for item in fixture.snapshots
    }
    evidence_ids = {
        item.key: StructuredLLMSemanticBackend._evidence_candidate_id(
            snapshot_ids[item.snapshot_key], item.text
        )
        for item in fixture.evidences
    }
    evidence_output = {
        "items": [
            {"text": item.text, "locator": item.locator, "context": item.context}
            for item in fixture.evidences
            if snapshot_ids[item.snapshot_key] in prepared.snapshot_ids
        ],
        "schema_id": "semantic.evidence-extraction",
        "schema_version": "1",
    }
    claim_items = []
    claim_ids = {}
    for item in fixture.claims:
        candidate = ClaimOutputItem(
            statement=item.statement,
            subject=item.subject,
            predicate=item.predicate,
            object=item.object,
            qualifiers=item.qualifiers,
            temporal_scope=item.temporal_scope,
            extraction_confidence=item.extraction_confidence,
            evidence_candidate_ids=[evidence_ids[key] for key in item.evidence_keys],
        )
        claim_ids[item.key] = stable_artifact_id(
            "semantic-claim-candidate",
            candidate.statement,
            candidate.subject,
            candidate.predicate,
            candidate.object,
            dict(candidate.qualifiers),
            candidate.temporal_scope,
        )
        claim_items.append(candidate.model_dump(mode="json"))
    claim_output = {
        "items": claim_items,
        "schema_id": "semantic.claim-extraction",
        "schema_version": "1",
    }
    relation_output = {
        "items": [
            {
                "evidence_candidate_id": evidence_ids[evidence_key],
                "claim_candidate_id": claim_ids[item.key],
                "relation": item.relation_for(evidence_key).value,
                "rationale": "provider semantic candidate",
            }
            for item in fixture.claims
            for evidence_key in item.evidence_keys
        ],
        "schema_id": "semantic.evidence-relation",
        "schema_version": "1",
    }
    dependency_output = {
        "items": [],
        "schema_id": "semantic.source-dependency",
        "schema_version": "1",
    }
    return [
        _provider_envelope(evidence_output),
        _provider_envelope(claim_output),
        _provider_envelope(relation_output),
        _provider_envelope(dependency_output),
    ]


@pytest.mark.parametrize(
    ("fixture_id", "expected_atom_status"),
    [("independent_support", "active"), ("qualified_support", "withheld")],
)
def test_provider_mock_structured_e2e_preserves_deterministic_publication(
    fixture_id: str, expected_atom_status: str, tmp_path
) -> None:
    fixture_backend = FixtureSemanticBackend()
    with SQLiteRepository(
        tmp_path / f"{fixture_id}.sqlite", tmp_path / f"{fixture_id}-snapshots"
    ) as repository:
        prepared = FixtureHarness(fixture_backend).prepare(repository, fixture_id)
        transport = ScriptedHTTPTransport(
            _semantic_provider_script(fixture_id, fixture_backend, prepared)
        )
        runtime = runtime_for(transport, tmp_path / f"{fixture_id}-traces")
        result = DeterministicRefinery(
            repository,
            StructuredLLMSemanticBackend(runtime),
            pipeline_version="phase1c-structured-llm-v1",
        ).run(
            prepared.snapshot_ids,
            reference_time=fixture_backend.get_fixture(fixture_id).created_at,
        )
        assert result.atoms[0].status.value == expected_atom_status
        assert len(runtime.records) == 4
        assert {record.stage_run_id for record in runtime.records} == {
            item.id
            for item in result.stage_runs
            if item.stage_name
            in {"evidence_extract", "claim_extract", "evidence_link", "independence"}
        }
