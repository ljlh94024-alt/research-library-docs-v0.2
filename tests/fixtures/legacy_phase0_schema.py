"""Independent reconstruction of the schema created by commit 01e0ce8.

This module intentionally does not import ``research_library.storage.schema``.
It is a parity oracle for the historical 0001 migration.
"""

from sqlalchemy import (
    JSON,
    Column,
    ForeignKey,
    Index,
    MetaData,
    String,
    Table,
    Text,
)


def create_legacy_01e0ce8_schema(engine) -> MetaData:
    metadata = MetaData()

    Table(
        "sources",
        metadata,
        Column("id", String(128), primary_key=True),
        Column("source_type", String(32), nullable=False),
        Column("canonical_uri", Text, nullable=False),
        Column("title", Text),
        Column("publisher", Text),
        Column("metadata", JSON, nullable=False),
        Column("created_at", String(64), nullable=False),
    )
    Table(
        "pipeline_runs",
        metadata,
        Column("id", String(128), primary_key=True),
        Column("pipeline_version", String(128), nullable=False),
        Column("status", String(32), nullable=False),
        Column("started_at", String(64), nullable=False),
        Column("finished_at", String(64)),
        Column("input_ref", Text),
        Column("output_ref", Text),
        Column("error", Text),
        Column("metadata", JSON, nullable=False),
    )
    Table(
        "stage_runs",
        metadata,
        Column("id", String(128), primary_key=True),
        Column("pipeline_run_id", String(128), ForeignKey("pipeline_runs.id"), nullable=False),
        Column("stage_name", String(128), nullable=False),
        Column("stage_version", String(128), nullable=False),
        Column("status", String(32), nullable=False),
        Column("model", String(128)),
        Column("provider", String(128)),
        Column("prompt_id", String(128)),
        Column("prompt_version", String(128)),
        Column("input_ref", Text),
        Column("output_ref", Text),
        Column("started_at", String(64), nullable=False),
        Column("finished_at", String(64)),
        Column("error_type", String(64)),
        Column("error", Text),
    )
    Table(
        "source_snapshots",
        metadata,
        Column("id", String(128), primary_key=True),
        Column("source_id", String(128), ForeignKey("sources.id"), nullable=False),
        Column("retrieved_at", String(64), nullable=False),
        Column("content_hash", String(64), nullable=False),
        Column("content_ref", Text, nullable=False, unique=True),
        Column("mime_type", String(128)),
        Column("metadata", JSON, nullable=False),
        Column("created_by_stage_run_id", String(128)),
    )
    Table(
        "evidence",
        metadata,
        Column("id", String(128), primary_key=True),
        Column("snapshot_id", String(128), ForeignKey("source_snapshots.id"), nullable=False),
        Column("text", Text, nullable=False),
        Column("locator", Text),
        Column("context", Text),
        Column("extraction_method", String(128)),
        Column("metadata", JSON, nullable=False),
        Column("created_at", String(64), nullable=False),
        Column("created_by_stage_run_id", String(128)),
    )
    Table(
        "claims",
        metadata,
        Column("id", String(128), primary_key=True),
        Column("statement", Text, nullable=False),
        Column("subject", Text),
        Column("predicate", Text),
        Column("object", Text),
        Column("qualifiers", JSON, nullable=False),
        Column("temporal_scope", Text),
        Column("extraction_confidence", String(32)),
        Column("created_at", String(64), nullable=False),
        Column("created_by_stage_run_id", String(128)),
    )
    Table(
        "claim_groups",
        metadata,
        Column("id", String(128), primary_key=True),
        Column("canonical_key", Text, nullable=False, unique=True),
        Column("name", Text),
        Column("created_at", String(64), nullable=False),
    )
    Table(
        "claim_group_members",
        metadata,
        Column("claim_group_id", String(128), ForeignKey("claim_groups.id"), primary_key=True),
        Column("claim_id", String(128), ForeignKey("claims.id"), primary_key=True),
    )
    Table(
        "evidence_links",
        metadata,
        Column("id", String(128), primary_key=True),
        Column("evidence_id", String(128), ForeignKey("evidence.id"), nullable=False),
        Column("claim_id", String(128), ForeignKey("claims.id"), nullable=False),
        Column("relation_type", String(32), nullable=False),
        Column("rationale", Text),
        Column("created_at", String(64), nullable=False),
        Column("created_by_stage_run_id", String(128)),
    )
    Table(
        "contradictions",
        metadata,
        Column("id", String(128), primary_key=True),
        Column("claim_a_id", String(128), ForeignKey("claims.id"), nullable=False),
        Column("claim_b_id", String(128), ForeignKey("claims.id"), nullable=False),
        Column("type", String(32), nullable=False),
        Column("severity", String(32), nullable=False),
        Column("reason", Text, nullable=False),
        Column("status", String(32), nullable=False),
        Column("created_at", String(64), nullable=False),
        Column("resolved_at", String(64)),
    )
    Table(
        "resolved_claims",
        metadata,
        Column("id", String(128), primary_key=True),
        Column("claim_group_id", String(128), ForeignKey("claim_groups.id"), nullable=False),
        Column("canonical_statement", Text, nullable=False),
        Column("status", String(64), nullable=False),
        Column("confidence", String(32)),
        Column("resolution_reason", Text),
        Column("validity", Text),
        Column("created_at", String(64), nullable=False),
        Column("created_by_stage_run_id", String(128)),
    )
    Table(
        "knowledge_atoms",
        metadata,
        Column("id", String(128), primary_key=True),
        Column(
            "resolved_claim_id",
            String(128),
            ForeignKey("resolved_claims.id"),
            nullable=False,
        ),
        Column("statement", Text, nullable=False),
        Column("confidence", String(32)),
        Column("qualifiers", JSON, nullable=False),
        Column("created_at", String(64), nullable=False),
        Column("created_by_stage_run_id", String(128)),
    )
    Table(
        "source_dependencies",
        metadata,
        Column("id", String(128), primary_key=True),
        Column("source_id", String(128), ForeignKey("sources.id"), nullable=False),
        Column("parent_source_id", String(128), ForeignKey("sources.id"), nullable=False),
        Column("dependency_group", String(128)),
        Column("independence_score", String(32)),
        Column("reason", Text),
    )
    Table(
        "human_overrides",
        metadata,
        Column("id", String(128), primary_key=True),
        Column("entity_type", String(64), nullable=False),
        Column("entity_id", String(128), nullable=False),
        Column("action", String(64), nullable=False),
        Column("payload", JSON, nullable=False),
        Column("created_at", String(64), nullable=False),
    )

    source_snapshots = metadata.tables["source_snapshots"]
    evidence = metadata.tables["evidence"]
    evidence_links = metadata.tables["evidence_links"]
    stage_runs = metadata.tables["stage_runs"]
    claims = metadata.tables["claims"]
    Index("ix_source_snapshots_source_id", source_snapshots.c.source_id)
    Index("ix_evidence_snapshot_id", evidence.c.snapshot_id)
    Index("ix_evidence_links_claim_id", evidence_links.c.claim_id)
    Index("ix_evidence_links_evidence_id", evidence_links.c.evidence_id)
    Index("ix_stage_runs_pipeline_run_id", stage_runs.c.pipeline_run_id)
    Index("ix_claims_statement", claims.c.statement)
    metadata.create_all(engine)
    return metadata
