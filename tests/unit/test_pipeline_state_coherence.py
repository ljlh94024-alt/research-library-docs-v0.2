from datetime import UTC, datetime, timedelta

import pytest

from research_library.domain import PipelineRun, PipelineRunStatus, StageRun, StageRunStatus

STARTED = datetime(2026, 1, 1, tzinfo=UTC)
FINISHED = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    "kwargs",
    (
        {"finished_at": FINISHED},
        {"output_ref": "output"},
        {"error": "error"},
        {"status": PipelineRunStatus.SUCCEEDED},
        {"status": PipelineRunStatus.SUCCEEDED, "finished_at": FINISHED, "error": "error"},
        {"status": PipelineRunStatus.FAILED, "finished_at": FINISHED},
        {
            "status": PipelineRunStatus.FAILED,
            "finished_at": STARTED - timedelta(seconds=1),
            "error": "error",
        },
    ),
)
def test_pipeline_run_rejects_incoherent_state(kwargs) -> None:
    with pytest.raises(ValueError):
        PipelineRun(id="coherent-pipeline", started_at=STARTED, **kwargs)


@pytest.mark.parametrize(
    "kwargs",
    (
        {"finished_at": FINISHED},
        {"error": "error"},
        {"error_type": "type"},
        {"status": StageRunStatus.SUCCEEDED},
        {"status": StageRunStatus.SUCCEEDED, "finished_at": FINISHED, "error": "error"},
        {"status": StageRunStatus.SUCCEEDED, "finished_at": FINISHED, "error_type": "type"},
        {"status": StageRunStatus.FAILED, "finished_at": FINISHED},
        {"status": StageRunStatus.FAILED, "finished_at": FINISHED, "error_type": "type"},
        {"status": StageRunStatus.FAILED, "finished_at": FINISHED, "error": "error"},
        {
            "status": StageRunStatus.FAILED,
            "finished_at": STARTED - timedelta(seconds=1),
            "error_type": "type",
            "error": "error",
        },
    ),
)
def test_stage_run_rejects_incoherent_state(kwargs) -> None:
    with pytest.raises(ValueError):
        StageRun(
            id="coherent-stage",
            pipeline_run_id="coherent-pipeline",
            stage_name="fixture",
            started_at=STARTED,
            **kwargs,
        )


def test_domain_accepts_coherent_terminal_states() -> None:
    succeeded_pipeline = PipelineRun(
        id="valid-succeeded-pipeline",
        started_at=STARTED,
        status=PipelineRunStatus.SUCCEEDED,
        finished_at=FINISHED,
    )
    failed_pipeline = PipelineRun(
        id="valid-failed-pipeline",
        started_at=STARTED,
        status=PipelineRunStatus.FAILED,
        finished_at=FINISHED,
        error="failure",
    )
    succeeded_stage = StageRun(
        id="valid-succeeded-stage",
        pipeline_run_id=succeeded_pipeline.id,
        stage_name="fixture",
        started_at=STARTED,
        status=StageRunStatus.SUCCEEDED,
        finished_at=FINISHED,
    )
    failed_stage = StageRun(
        id="valid-failed-stage",
        pipeline_run_id=failed_pipeline.id,
        stage_name="fixture",
        started_at=STARTED,
        status=StageRunStatus.FAILED,
        finished_at=FINISHED,
        error_type="fixture_error",
        error="failure",
    )
    assert succeeded_pipeline.finished_at == FINISHED
    assert failed_pipeline.error == "failure"
    assert succeeded_stage.status is StageRunStatus.SUCCEEDED
    assert failed_stage.error_type == "fixture_error"
