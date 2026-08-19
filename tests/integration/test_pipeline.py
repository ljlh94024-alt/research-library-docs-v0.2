import pytest

from research_library.domain import PipelineRunStatus, StageRunStatus
from research_library.refinery import PipelineRunner


def test_pipeline_run_and_stage_history_are_persisted(repository) -> None:
    runner = PipelineRunner(repository, pipeline_version="phase0-test")
    first = runner.start_run(input_ref="fixture://one")
    stage = runner.start_stage(first, "fixture_stage", stage_version="1")
    succeeded_stage = runner.succeed_stage(stage, output_ref="fixture://output")
    runner.finish_run(first, output_ref="fixture://output")

    second = runner.start_run(input_ref="fixture://two")
    runner.finish_run(second, output_ref="fixture://output-two")

    assert repository.get_pipeline_run(first.id).status is PipelineRunStatus.SUCCEEDED
    assert repository.get_stage_run(stage.id).status is StageRunStatus.SUCCEEDED
    assert succeeded_stage.output_ref == "fixture://output"
    assert len(repository.list_pipeline_runs()) == 2


def test_failed_stage_is_recorded_and_exception_is_not_swallowed(repository) -> None:
    runner = PipelineRunner(repository)
    run = runner.start_run()
    with pytest.raises(RuntimeError, match="fixture failure"):
        runner.run_stage(
            run, "failing_fixture", lambda: (_ for _ in ()).throw(RuntimeError("fixture failure"))
        )

    saved_run = repository.get_pipeline_run(run.id)
    saved_stage = repository.list_stage_runs(run.id)[0]
    assert saved_run.status is PipelineRunStatus.FAILED
    assert saved_stage.status is StageRunStatus.FAILED
    assert saved_stage.error == "fixture failure"
