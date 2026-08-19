import json
from datetime import UTC, datetime, timedelta

import pytest

from research_library.domain import PipelineRun, StageRun, StageRunStatus
from research_library.llm import (
    LLMCallRecord,
    LLMCallStatus,
    LLMClientRegistry,
    LLMTraceStore,
    ScriptedFakeLLMClient,
    StructuredLLMRuntime,
)
from research_library.refinery import (
    CANONICAL_STAGE_NAMES,
    DeterministicRefinery,
    FixtureHarness,
    FixtureSemanticBackend,
    SemanticRequest,
    StructuredLLMSemanticBackend,
)


def test_llm_call_repository_is_append_only_and_provenance_exposes_calls(repository) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    repository.save_pipeline_run(
        PipelineRun(id="audit-pipeline", pipeline_version="phase1c", started_at=now)
    )
    repository.save_stage_run(
        StageRun(
            id="audit-stage",
            pipeline_run_id="audit-pipeline",
            stage_name="evidence_extract",
            stage_version="phase1c",
            status=StageRunStatus.STARTED,
            started_at=now,
        )
    )
    record = LLMCallRecord(
        id="audit-call",
        logical_request_id="audit-logical",
        stage_run_id="audit-stage",
        task_type="evidence_extract",
        provider="fake",
        model="fake",
        model_role="extractor",
        prompt_id="semantic.evidence_extract",
        prompt_version="v1",
        schema_id="semantic.evidence-extraction",
        schema_version="1",
        attempt=1,
        status=LLMCallStatus.SUCCEEDED,
        request_id="request-1",
        request_hash="a" * 64,
        response_hash="b" * 64,
        request_ref="llm-trace:" + "a" * 64,
        response_ref="llm-trace:" + "b" * 64,
        input_tokens=2,
        output_tokens=3,
        total_tokens=5,
        latency_ms=1.5,
        started_at=now,
        finished_at=now + timedelta(milliseconds=2),
    )
    assert repository.save_llm_call(record) == record
    assert repository.get_llm_call(record.id) == record
    assert repository.list_llm_calls(logical_request_id="audit-logical") == (record,)
    with pytest.raises(Exception):
        repository.save_llm_call(record.__class__(**{**record.to_dict(), "request_hash": "c" * 64}))


def _structured_fixture(repository, tmp_path, fixture_id: str):
    fixture_backend = FixtureSemanticBackend()
    fixture = fixture_backend.get_fixture(fixture_id)
    prepared = FixtureHarness(fixture_backend).prepare(repository, fixture_id)
    batch = fixture_backend.collect(SemanticRequest(prepared.snapshot_ids), repository)
    structured_type = StructuredLLMSemanticBackend
    evidence_ids = [
        structured_type._evidence_candidate_id(item.snapshot_id, item.text)
        for item in batch.evidence
    ]
    evidence_key_to_id = {
        item.candidate_id: evidence_ids[index] for index, item in enumerate(batch.evidence)
    }
    claim_ids = [structured_type._claim_candidate_id(item) for item in batch.claims]
    claim_key_to_id = {
        item.candidate_id: claim_ids[index] for index, item in enumerate(batch.claims)
    }
    responses = [
        json.dumps(
            {
                "items": [
                    {"text": item.text, "locator": item.locator, "context": item.context}
                    for item in batch.evidence
                ]
            }
        ),
        json.dumps(
            {
                "items": [
                    {
                        "statement": item.statement,
                        "subject": item.subject,
                        "predicate": item.predicate,
                        "object": item.object,
                        "qualifiers": dict(item.qualifiers),
                        "temporal_scope": item.temporal_scope,
                        "extraction_confidence": item.extraction_confidence,
                        "evidence_candidate_ids": [
                            evidence_key_to_id[key] for key in item.evidence_candidate_ids
                        ],
                    }
                    for item in batch.claims
                ]
            }
        ),
        json.dumps(
            {
                "items": [
                    {
                        "evidence_candidate_id": evidence_key_to_id[item.evidence_candidate_id],
                        "claim_candidate_id": claim_key_to_id[item.claim_candidate_id],
                        "relation": item.relation_type.value,
                        "rationale": item.rationale,
                    }
                    for item in batch.relations
                ]
            }
        ),
        json.dumps(
            {
                "items": [
                    {
                        "source_id": item.source_id,
                        "parent_source_id": item.parent_source_id,
                        "relation_type": item.relation_type.value,
                        "dependency_group": item.dependency_group,
                        "independence_score": item.independence_score,
                        "reason": item.reason,
                        "signals": dict(item.signals),
                    }
                    for item in batch.dependencies
                ]
            }
        ),
    ]
    clients = LLMClientRegistry()
    clients.register("fake", ScriptedFakeLLMClient(responses))
    runtime = StructuredLLMRuntime(
        clients=clients,
        trace_store=LLMTraceStore(tmp_path / "llm-traces"),
        repository=repository,
    )
    result = DeterministicRefinery(
        repository,
        StructuredLLMSemanticBackend(runtime),
        pipeline_version="phase1c-structured-llm-v1",
    ).run(prepared.snapshot_ids, reference_time=fixture.created_at)
    return result, runtime


@pytest.mark.parametrize("fixture_id", ["independent_support", "qualified_support"])
def test_structured_backend_preserves_deterministic_semantic_signature(
    repository, tmp_path, fixture_id
) -> None:
    result, runtime = _structured_fixture(repository, tmp_path, fixture_id)
    assert result.semantic_signature
    assert len(runtime.records) == 4
    assert {item.stage_run_id for item in runtime.records} == {
        item.id
        for item in result.stage_runs
        if item.stage_name in {"evidence_extract", "claim_extract", "evidence_link", "independence"}
    }
    assert all(item.status is LLMCallStatus.SUCCEEDED for item in runtime.records)
    assert result.decisions[0].status.value in {"resolved", "insufficient_evidence"}
    assert result.atoms[0].status.value in {"active", "withheld"}


def test_structured_failure_marks_stage_and_pipeline_failed(repository, tmp_path) -> None:
    fixture_backend = FixtureSemanticBackend()
    prepared = FixtureHarness(fixture_backend).prepare(repository, "independent_support")
    clients = LLMClientRegistry()
    clients.register("fake", ScriptedFakeLLMClient(["not-json", "still-not-json"]))
    runtime = StructuredLLMRuntime(
        clients=clients,
        trace_store=LLMTraceStore(tmp_path / "failure-traces"),
        repository=repository,
    )
    with pytest.raises(Exception):
        DeterministicRefinery(
            repository,
            StructuredLLMSemanticBackend(runtime),
            pipeline_version="phase1c-structured-llm-v1",
        ).run(
            prepared.snapshot_ids,
            reference_time=fixture_backend.get_fixture("independent_support").created_at,
        )
    pipeline = repository.list_pipeline_runs()[0]
    assert pipeline.status.value == "failed"
    stage = repository.list_stage_runs(pipeline.id)[0]
    assert stage.stage_name == "evidence_extract"
    assert stage.status.value == "failed"
    assert len(repository.list_llm_calls(stage_run_id=stage.id)) == 2
    assert len(repository.list_stage_runs(pipeline.id)) == 1


def test_phase1b_five_golden_results_remain_exact(repository) -> None:
    expected = {
        "independent_support": ("resolved", True, 0.98, "active"),
        "multi_repost_same_origin": ("resolved", False, 0.65, "withheld"),
        "direct_conflict": ("conflicting", True, 0.30, "withheld"),
        "qualified_support": ("insufficient_evidence", False, 0.40, "withheld"),
    }
    runner = DeterministicRefinery(repository, FixtureSemanticBackend())
    for fixture_id, (status, floor, score, atom_status) in expected.items():
        result = runner.run_fixture(fixture_id)
        assert result.decisions[0].status.value == status
        assert result.assessments[0].evidence_floor_met is floor
        assert result.assessments[0].score == score
        assert result.atoms[0].status.value == atom_status
        assert {item.stage_name for item in result.stage_runs} == set(CANONICAL_STAGE_NAMES)


def test_structured_processing_provenance_exposes_only_owned_stage_calls(
    repository, tmp_path
) -> None:
    result, _runtime = _structured_fixture(repository, tmp_path, "independent_support")
    provenance = repository.get_processing_provenance(result.atoms[0].id)
    calls_by_stage = {step.stage_run.stage_name: step.llm_calls for step in provenance.steps}
    assert len(calls_by_stage["evidence_extract"]) == 1
    assert len(calls_by_stage["claim_extract"]) == 1
    assert len(calls_by_stage["evidence_link"]) == 1
    assert len(calls_by_stage["independence"]) == 1
    assert not calls_by_stage.get("normalize", ())
    assert not calls_by_stage.get("contradiction", ())
    assert not calls_by_stage.get("resolve", ())
    assert not calls_by_stage.get("confidence", ())
    assert not calls_by_stage.get("atom_build", ())
