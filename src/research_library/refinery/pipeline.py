"""Minimal persistent pipeline execution skeleton."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from research_library.domain import (
    PipelineRun,
    PipelineRunStatus,
    StageRun,
    StageRunStatus,
)
from research_library.storage.repository import Repository


class PipelineRunner:
    """Create and persist runs without implementing Phase 1 refinery stages."""

    def __init__(self, repository: Repository, pipeline_version: str = "phase0") -> None:
        self.repository = repository
        self.pipeline_version = pipeline_version

    def start_run(
        self, *, input_ref: str | None = None, metadata: dict[str, Any] | None = None
    ) -> PipelineRun:
        run = PipelineRun(
            pipeline_version=self.pipeline_version,
            input_ref=input_ref,
            metadata=metadata or {},
        )
        return self.repository.save_pipeline_run(run)

    def start_stage(
        self,
        pipeline_run: PipelineRun,
        stage_name: str,
        *,
        stage_version: str = "phase0",
        input_ref: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        prompt_id: str | None = None,
        prompt_version: str | None = None,
    ) -> StageRun:
        stage = StageRun(
            pipeline_run_id=pipeline_run.id,
            stage_name=stage_name,
            stage_version=stage_version,
            input_ref=input_ref,
            model=model,
            provider=provider,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
        )
        return self.repository.save_stage_run(stage)

    def succeed_stage(self, stage: StageRun, *, output_ref: str | None = None) -> StageRun:
        finished = replace(
            stage,
            status=StageRunStatus.SUCCEEDED,
            output_ref=output_ref,
            finished_at=datetime.now(UTC),
        )
        return self.repository.save_stage_run(finished)

    def fail_stage(
        self,
        stage: StageRun,
        error: BaseException | str,
        *,
        error_type: str = "internal_error",
    ) -> StageRun:
        failed = replace(
            stage,
            status=StageRunStatus.FAILED,
            error_type=error_type,
            error=str(error),
            finished_at=datetime.now(UTC),
        )
        return self.repository.save_stage_run(failed)

    def finish_run(
        self,
        pipeline_run: PipelineRun,
        *,
        output_ref: str | None = None,
        error: str | None = None,
    ) -> PipelineRun:
        status = PipelineRunStatus.FAILED if error else PipelineRunStatus.SUCCEEDED
        finished = replace(
            pipeline_run,
            status=status,
            finished_at=datetime.now(UTC),
            output_ref=output_ref,
            error=error,
        )
        return self.repository.save_pipeline_run(finished)

    def run_stage(
        self,
        pipeline_run: PipelineRun,
        stage_name: str,
        operation: Callable[[], Any],
        *,
        stage_version: str = "phase0",
        input_ref: str | None = None,
        output_ref: str | None = None,
    ) -> Any:
        stage = self.start_stage(
            pipeline_run,
            stage_name,
            stage_version=stage_version,
            input_ref=input_ref,
        )
        try:
            result = operation()
        except Exception as exc:
            self.fail_stage(stage, exc)
            self.finish_run(pipeline_run, error=str(exc))
            raise
        self.succeed_stage(stage, output_ref=output_ref)
        return result
