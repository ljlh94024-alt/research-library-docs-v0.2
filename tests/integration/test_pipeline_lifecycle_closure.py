from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from research_library.domain import (
    PipelineRun,
    PipelineRunStatus,
    StageRun,
    StageRunStatus,
)
from research_library.storage import InvalidStateTransitionError, StorageIntegrityError

TIMESTAMP = datetime(2026, 1, 1, tzinfo=UTC)
FINISHED = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)


def _failed_stage(stage: StageRun) -> StageRun:
    return replace(
        stage,
        status=StageRunStatus.FAILED,
        finished_at=stage.started_at + timedelta(minutes=1),
        error_type="fixture_error",
        error="fixture failure",
    )


def _succeeded_stage(stage: StageRun) -> StageRun:
    return replace(
        stage,
        status=StageRunStatus.SUCCEEDED,
        finished_at=stage.started_at + timedelta(minutes=1),
    )


def test_new_pipeline_and_stage_must_start(repository) -> None:
    terminal_pipeline = PipelineRun(
        id="terminal-at-create-pipeline",
        status=PipelineRunStatus.SUCCEEDED,
        started_at=TIMESTAMP,
        finished_at=FINISHED,
    )
    with pytest.raises(InvalidStateTransitionError, match="must start in STARTED"):
        repository.save_pipeline_run(terminal_pipeline)

    parent = repository.save_pipeline_run(PipelineRun(id="terminal-stage-parent"))
    terminal_stage = StageRun(
        id="terminal-at-create-stage",
        pipeline_run_id=parent.id,
        stage_name="fixture",
        status=StageRunStatus.SUCCEEDED,
        started_at=TIMESTAMP,
        finished_at=FINISHED,
    )
    with pytest.raises(InvalidStateTransitionError, match="must start in STARTED"):
        repository.save_stage_run(terminal_stage)


def test_stage_creation_requires_existing_started_pipeline(repository) -> None:
    with pytest.raises(StorageIntegrityError, match="pipeline run does not exist"):
        repository.save_stage_run(
            StageRun(
                id="stage-without-pipeline",
                pipeline_run_id="missing-pipeline",
                stage_name="fixture",
            )
        )

    succeeded = repository.save_pipeline_run(
        PipelineRun(id="closed-pipeline", started_at=TIMESTAMP)
    )
    repository.save_pipeline_run(
        replace(succeeded, status=PipelineRunStatus.SUCCEEDED, finished_at=FINISHED)
    )
    with pytest.raises(InvalidStateTransitionError, match="terminal"):
        repository.save_stage_run(
            StageRun(
                id="stage-under-closed-pipeline",
                pipeline_run_id=succeeded.id,
                stage_name="fixture",
            )
        )


def test_new_stage_is_rejected_after_succeeded_or_failed_pipeline(repository) -> None:
    for pipeline_id, status, error in (
        ("succeeded-parent", PipelineRunStatus.SUCCEEDED, None),
        ("failed-parent", PipelineRunStatus.FAILED, "pipeline failure"),
    ):
        run = repository.save_pipeline_run(PipelineRun(id=pipeline_id, started_at=TIMESTAMP))
        repository.save_pipeline_run(
            replace(run, status=status, finished_at=FINISHED, error=error)
        )
        with pytest.raises(InvalidStateTransitionError):
            repository.save_stage_run(
                StageRun(
                    id=f"late-stage-{pipeline_id}",
                    pipeline_run_id=run.id,
                    stage_name="late",
                )
            )


def test_pipeline_success_requires_all_children_succeeded(repository) -> None:
    active_run = repository.save_pipeline_run(
        PipelineRun(id="active-child-run", started_at=TIMESTAMP)
    )
    active_stage = repository.save_stage_run(
        StageRun(id="active-child-stage", pipeline_run_id=active_run.id, stage_name="fixture")
    )
    with pytest.raises(InvalidStateTransitionError):
        repository.save_pipeline_run(
            replace(active_run, status=PipelineRunStatus.SUCCEEDED, finished_at=FINISHED)
        )
    with pytest.raises(InvalidStateTransitionError):
        repository.save_pipeline_run(
            replace(
                active_run,
                status=PipelineRunStatus.FAILED,
                finished_at=FINISHED,
                error="pipeline failure",
            )
        )
    assert repository.get_stage_run(active_stage.id).status is StageRunStatus.STARTED

    failed_run = repository.save_pipeline_run(
        PipelineRun(id="failed-child-run", started_at=TIMESTAMP)
    )
    failed_stage = repository.save_stage_run(
        StageRun(id="failed-child-stage", pipeline_run_id=failed_run.id, stage_name="fixture")
    )
    repository.save_stage_run(_failed_stage(failed_stage))
    with pytest.raises(InvalidStateTransitionError):
        repository.save_pipeline_run(
            replace(failed_run, status=PipelineRunStatus.SUCCEEDED, finished_at=FINISHED)
        )


def test_pipeline_terminal_transitions_allow_only_coherent_children(repository) -> None:
    success_run = repository.save_pipeline_run(
        PipelineRun(id="coherent-success", started_at=TIMESTAMP)
    )
    success_stage = repository.save_stage_run(
        StageRun(id="coherent-success-stage", pipeline_run_id=success_run.id, stage_name="fixture")
    )
    repository.save_stage_run(_succeeded_stage(success_stage))
    saved_success = repository.save_pipeline_run(
        replace(success_run, status=PipelineRunStatus.SUCCEEDED, finished_at=FINISHED)
    )
    assert saved_success.status is PipelineRunStatus.SUCCEEDED

    failure_run = repository.save_pipeline_run(
        PipelineRun(id="coherent-failure", started_at=TIMESTAMP)
    )
    failure_stage = repository.save_stage_run(
        StageRun(id="coherent-failure-stage", pipeline_run_id=failure_run.id, stage_name="fixture")
    )
    repository.save_stage_run(_failed_stage(failure_stage))
    saved_failure = repository.save_pipeline_run(
        replace(
            failure_run,
            status=PipelineRunStatus.FAILED,
            finished_at=FINISHED,
            error="pipeline failure",
        )
    )
    assert saved_failure.status is PipelineRunStatus.FAILED
