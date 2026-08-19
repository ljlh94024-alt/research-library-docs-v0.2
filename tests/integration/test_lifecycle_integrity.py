from dataclasses import replace
from datetime import UTC, datetime

import pytest

from research_library.domain import (
    Claim,
    Contradiction,
    ContradictionStatus,
    ContradictionType,
    PipelineRun,
    PipelineRunStatus,
    Source,
    SourceType,
    StageRun,
    StageRunStatus,
)
from research_library.storage import ImmutableRecordError, InvalidStateTransitionError

TIMESTAMP = datetime(2026, 1, 1, tzinfo=UTC)


def test_source_identity_is_immutable_but_descriptive_fields_are_mutable(repository) -> None:
    source = repository.save_source(
        Source(
            id="source-lifecycle",
            source_type=SourceType.PAPER,
            canonical_uri="https://example.test/one",
            created_at=TIMESTAMP,
        )
    )
    updated = replace(source, title="new title", publisher="publisher", metadata={"v": 2})
    assert repository.save_source(updated).title == "new title"
    for divergent in (
        replace(source, source_type=SourceType.WEB),
        replace(source, canonical_uri="https://example.test/two"),
        replace(source, created_at=datetime(2026, 1, 2, tzinfo=UTC)),
    ):
        with pytest.raises(ImmutableRecordError):
            repository.save_source(divergent)


def test_contradiction_identity_and_terminal_transitions_are_protected(repository) -> None:
    claim_a = repository.save_claim(Claim(id="contradiction-claim-a", statement="one"))
    claim_b = repository.save_claim(Claim(id="contradiction-claim-b", statement="two"))
    contradiction = repository.save_contradiction(
        Contradiction(
            id="contradiction-lifecycle",
            claim_a_id=claim_a.id,
            claim_b_id=claim_b.id,
            type=ContradictionType.DIRECT,
            reason="initial",
            created_at=TIMESTAMP,
        )
    )
    resolved = replace(
        contradiction,
        severity=contradiction.severity,
        reason="reviewed",
        status=ContradictionStatus.RESOLVED,
        resolved_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    repository.save_contradiction(resolved)
    assert repository.get_contradiction(contradiction.id).status is ContradictionStatus.RESOLVED
    assert repository.save_contradiction(resolved) == resolved

    with pytest.raises(ImmutableRecordError):
        repository.save_contradiction(replace(resolved, claim_a_id="other-claim"))
    with pytest.raises(ImmutableRecordError):
        repository.save_contradiction(replace(resolved, type=ContradictionType.TEMPORAL))
    with pytest.raises(InvalidStateTransitionError):
        repository.save_contradiction(replace(resolved, status=ContradictionStatus.OPEN))
    with pytest.raises(InvalidStateTransitionError):
        repository.save_contradiction(replace(resolved, status=ContradictionStatus.DISMISSED))


def test_pipeline_run_identity_and_terminal_lifecycle_are_protected(repository) -> None:
    run = repository.save_pipeline_run(
        PipelineRun(
            id="pipeline-lifecycle",
            pipeline_version="v1",
            started_at=TIMESTAMP,
            input_ref="input-v1",
            metadata={"source": "fixture"},
        )
    )
    finished = replace(
        run,
        status=PipelineRunStatus.SUCCEEDED,
        finished_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
        output_ref="output-v1",
    )
    repository.save_pipeline_run(finished)
    assert repository.save_pipeline_run(finished) == finished
    with pytest.raises(ImmutableRecordError):
        repository.save_pipeline_run(replace(run, pipeline_version="v2"))
    with pytest.raises(ImmutableRecordError):
        repository.save_pipeline_run(replace(run, started_at=datetime(2026, 1, 2, tzinfo=UTC)))
    with pytest.raises(InvalidStateTransitionError):
        repository.save_pipeline_run(
            replace(finished, status=PipelineRunStatus.STARTED, finished_at=None, output_ref=None)
        )
    with pytest.raises(InvalidStateTransitionError):
        repository.save_pipeline_run(
            replace(finished, status=PipelineRunStatus.FAILED, error="different terminal")
        )
    with pytest.raises(InvalidStateTransitionError):
        repository.save_pipeline_run(replace(finished, output_ref="changed-output"))


def test_stage_run_identity_includes_model_prompt_and_pipeline_link(repository) -> None:
    run_a = repository.save_pipeline_run(
        PipelineRun(id="stage-pipeline-a", pipeline_version="v1", started_at=TIMESTAMP)
    )
    run_b = repository.save_pipeline_run(
        PipelineRun(id="stage-pipeline-b", pipeline_version="v1", started_at=TIMESTAMP)
    )
    stage = repository.save_stage_run(
        StageRun(
            id="stage-lifecycle",
            pipeline_run_id=run_a.id,
            stage_name="extract",
            stage_version="v1",
            model="model-a",
            provider="fake",
            prompt_id="prompt-a",
            prompt_version="1",
            input_ref="input-a",
            started_at=TIMESTAMP,
        )
    )
    started_update = replace(stage, output_ref="intermediate")
    repository.save_stage_run(started_update)
    for divergent in (
        replace(stage, pipeline_run_id=run_b.id),
        replace(stage, stage_name="other"),
        replace(stage, stage_version="v2"),
        replace(stage, model="model-b"),
        replace(stage, prompt_id="prompt-b"),
        replace(stage, input_ref="input-b"),
    ):
        with pytest.raises(ImmutableRecordError):
            repository.save_stage_run(divergent)

    succeeded = replace(
        stage,
        status=StageRunStatus.SUCCEEDED,
        finished_at=datetime(2026, 1, 1, 0, 2, tzinfo=UTC),
        output_ref="output-a",
    )
    repository.save_stage_run(succeeded)
    assert repository.save_stage_run(succeeded) == succeeded
    with pytest.raises(InvalidStateTransitionError):
        repository.save_stage_run(
            replace(succeeded, status=StageRunStatus.STARTED, finished_at=None, output_ref=None)
        )
    with pytest.raises(InvalidStateTransitionError):
        repository.save_stage_run(
            replace(
                succeeded,
                status=StageRunStatus.FAILED,
                error_type="different_terminal",
                error="different terminal",
            )
        )
    with pytest.raises(InvalidStateTransitionError):
        repository.save_stage_run(replace(succeeded, output_ref="changed-output"))
