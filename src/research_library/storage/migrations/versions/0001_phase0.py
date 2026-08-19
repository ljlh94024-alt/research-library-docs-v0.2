"""Create the original, frozen Phase 0 relational schema.

This revision is historical.  It intentionally spells out the schema that was
first published instead of importing the current SQLAlchemy metadata.  Future
schema changes belong in new revisions.
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_phase0"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("canonical_uri", sa.Text, nullable=False),
        sa.Column("title", sa.Text),
        sa.Column("publisher", sa.Text),
        sa.Column("metadata", sa.JSON, nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
    )
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("pipeline_version", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.String(64), nullable=False),
        sa.Column("finished_at", sa.String(64)),
        sa.Column("input_ref", sa.Text),
        sa.Column("output_ref", sa.Text),
        sa.Column("error", sa.Text),
        sa.Column("metadata", sa.JSON, nullable=False),
    )
    op.create_table(
        "stage_runs",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("pipeline_run_id", sa.String(128), nullable=False),
        sa.Column("stage_name", sa.String(128), nullable=False),
        sa.Column("stage_version", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("model", sa.String(128)),
        sa.Column("provider", sa.String(128)),
        sa.Column("prompt_id", sa.String(128)),
        sa.Column("prompt_version", sa.String(128)),
        sa.Column("input_ref", sa.Text),
        sa.Column("output_ref", sa.Text),
        sa.Column("started_at", sa.String(64), nullable=False),
        sa.Column("finished_at", sa.String(64)),
        sa.Column("error_type", sa.String(64)),
        sa.Column("error", sa.Text),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"]),
    )
    op.create_table(
        "source_snapshots",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("retrieved_at", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("content_ref", sa.Text, nullable=False),
        sa.Column("mime_type", sa.String(128)),
        sa.Column("metadata", sa.JSON, nullable=False),
        sa.Column("created_by_stage_run_id", sa.String(128)),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.UniqueConstraint("content_ref"),
    )
    op.create_table(
        "evidence",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("snapshot_id", sa.String(128), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("locator", sa.Text),
        sa.Column("context", sa.Text),
        sa.Column("extraction_method", sa.String(128)),
        sa.Column("metadata", sa.JSON, nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("created_by_stage_run_id", sa.String(128)),
        sa.ForeignKeyConstraint(["snapshot_id"], ["source_snapshots.id"]),
    )
    op.create_table(
        "claims",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("statement", sa.Text, nullable=False),
        sa.Column("subject", sa.Text),
        sa.Column("predicate", sa.Text),
        sa.Column("object", sa.Text),
        sa.Column("qualifiers", sa.JSON, nullable=False),
        sa.Column("temporal_scope", sa.Text),
        sa.Column("extraction_confidence", sa.String(32)),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("created_by_stage_run_id", sa.String(128)),
    )
    op.create_table(
        "claim_groups",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("canonical_key", sa.Text, nullable=False),
        sa.Column("name", sa.Text),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.UniqueConstraint("canonical_key"),
    )
    op.create_table(
        "claim_group_members",
        sa.Column("claim_group_id", sa.String(128), primary_key=True),
        sa.Column("claim_id", sa.String(128), primary_key=True),
        sa.ForeignKeyConstraint(["claim_group_id"], ["claim_groups.id"]),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
    )
    op.create_table(
        "evidence_links",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("evidence_id", sa.String(128), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("relation_type", sa.String(32), nullable=False),
        sa.Column("rationale", sa.Text),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("created_by_stage_run_id", sa.String(128)),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence.id"]),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
    )
    op.create_table(
        "contradictions",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("claim_a_id", sa.String(128), nullable=False),
        sa.Column("claim_b_id", sa.String(128), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("resolved_at", sa.String(64)),
        sa.ForeignKeyConstraint(["claim_a_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["claim_b_id"], ["claims.id"]),
    )
    op.create_table(
        "resolved_claims",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("claim_group_id", sa.String(128), nullable=False),
        sa.Column("canonical_statement", sa.Text, nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("confidence", sa.String(32)),
        sa.Column("resolution_reason", sa.Text),
        sa.Column("validity", sa.Text),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("created_by_stage_run_id", sa.String(128)),
        sa.ForeignKeyConstraint(["claim_group_id"], ["claim_groups.id"]),
    )
    op.create_table(
        "knowledge_atoms",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("resolved_claim_id", sa.String(128), nullable=False),
        sa.Column("statement", sa.Text, nullable=False),
        sa.Column("confidence", sa.String(32)),
        sa.Column("qualifiers", sa.JSON, nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("created_by_stage_run_id", sa.String(128)),
        sa.ForeignKeyConstraint(["resolved_claim_id"], ["resolved_claims.id"]),
    )
    op.create_table(
        "source_dependencies",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("parent_source_id", sa.String(128), nullable=False),
        sa.Column("dependency_group", sa.String(128)),
        sa.Column("independence_score", sa.String(32)),
        sa.Column("reason", sa.Text),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.ForeignKeyConstraint(["parent_source_id"], ["sources.id"]),
    )
    op.create_table(
        "human_overrides",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
    )
    op.create_index("ix_source_snapshots_source_id", "source_snapshots", ["source_id"])
    op.create_index("ix_evidence_snapshot_id", "evidence", ["snapshot_id"])
    op.create_index("ix_evidence_links_claim_id", "evidence_links", ["claim_id"])
    op.create_index("ix_evidence_links_evidence_id", "evidence_links", ["evidence_id"])
    op.create_index("ix_stage_runs_pipeline_run_id", "stage_runs", ["pipeline_run_id"])
    op.create_index("ix_claims_statement", "claims", ["statement"])


def downgrade() -> None:
    for name, table in (
        ("ix_claims_statement", "claims"),
        ("ix_stage_runs_pipeline_run_id", "stage_runs"),
        ("ix_evidence_links_evidence_id", "evidence_links"),
        ("ix_evidence_links_claim_id", "evidence_links"),
        ("ix_evidence_snapshot_id", "evidence"),
        ("ix_source_snapshots_source_id", "source_snapshots"),
    ):
        op.drop_index(name, table_name=table)
    for table in (
        "human_overrides",
        "source_dependencies",
        "knowledge_atoms",
        "resolved_claims",
        "contradictions",
        "evidence_links",
        "claim_group_members",
        "claim_groups",
        "claims",
        "evidence",
        "source_snapshots",
        "stage_runs",
        "pipeline_runs",
        "sources",
    ):
        op.drop_table(table)
