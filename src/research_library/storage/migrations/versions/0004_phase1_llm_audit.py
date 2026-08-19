"""Add immutable structured LLM call audit records."""

import sqlalchemy as sa
from alembic import op

revision = "0004_phase1_llm_audit"
down_revision = "0003_phase1_refinery_domain"
branch_labels = None
depends_on = None


_INDEXES = (
    ("ix_llm_calls_stage_run_id", "stage_run_id"),
    ("ix_llm_calls_logical_request_id", "logical_request_id"),
    ("ix_llm_calls_prompt", ["prompt_id", "prompt_version"]),
    ("ix_llm_calls_provider_model", ["provider", "model"]),
)


def upgrade() -> None:
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("logical_request_id", sa.String(128), nullable=False),
        sa.Column("stage_run_id", sa.String(128), nullable=False),
        sa.Column("task_type", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("model", sa.String(256), nullable=False),
        sa.Column("model_role", sa.String(64), nullable=False),
        sa.Column("prompt_id", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("schema_id", sa.String(128), nullable=False),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("attempt", sa.Integer, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("request_id", sa.String(256)),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_hash", sa.String(64)),
        sa.Column("request_ref", sa.Text, nullable=False),
        sa.Column("response_ref", sa.Text),
        sa.Column("input_tokens", sa.Integer),
        sa.Column("output_tokens", sa.Integer),
        sa.Column("total_tokens", sa.Integer),
        sa.Column("latency_ms", sa.Float, nullable=False),
        sa.Column("started_at", sa.String(64), nullable=False),
        sa.Column("finished_at", sa.String(64), nullable=False),
        sa.Column("error_type", sa.String(128)),
        sa.Column("error", sa.Text),
        sa.Column("metadata", sa.JSON, nullable=False),
        sa.ForeignKeyConstraint(["stage_run_id"], ["stage_runs.id"]),
        sa.UniqueConstraint(
            "logical_request_id", "attempt", name="uq_llm_calls_logical_request_attempt"
        ),
        sa.CheckConstraint("attempt >= 1", name="ck_llm_calls_attempt_positive"),
        sa.CheckConstraint("latency_ms >= 0.0", name="ck_llm_calls_latency_nonnegative"),
        sa.CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_llm_calls_input_tokens_nonnegative",
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_llm_calls_output_tokens_nonnegative",
        ),
        sa.CheckConstraint(
            "total_tokens IS NULL OR total_tokens >= 0",
            name="ck_llm_calls_total_tokens_nonnegative",
        ),
    )
    for name, columns in _INDEXES:
        op.create_index(name, "llm_calls", columns if isinstance(columns, list) else [columns])


def downgrade() -> None:
    for name, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name="llm_calls")
    op.drop_table("llm_calls")
