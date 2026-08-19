"""SQLAlchemy Core schema used by the versioned migration and repository.

The tables in this module are infrastructure representations.  They are not
the domain objects exported from ``research_library.domain``.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()

sources = Table(
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

pipeline_runs = Table(
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

stage_runs = Table(
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

source_snapshots = Table(
    "source_snapshots",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("source_id", String(128), ForeignKey("sources.id"), nullable=False),
    Column("retrieved_at", String(64), nullable=False),
    Column("content_hash", String(64), nullable=False),
    Column("content_ref", Text, nullable=False, unique=True),
    Column("mime_type", String(128)),
    Column("metadata", JSON, nullable=False),
    Column("created_by_stage_run_id", String(128), ForeignKey("stage_runs.id")),
)

evidence = Table(
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
    Column("created_by_stage_run_id", String(128), ForeignKey("stage_runs.id")),
)

claims = Table(
    "claims",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("statement", Text, nullable=False),
    Column("subject", Text),
    Column("predicate", Text),
    Column("object", Text),
    Column("qualifiers", JSON, nullable=False),
    Column("temporal_scope", Text),
    Column("extraction_confidence", Float),
    Column("created_at", String(64), nullable=False),
    Column("created_by_stage_run_id", String(128), ForeignKey("stage_runs.id")),
    CheckConstraint(
        "extraction_confidence IS NULL OR "
        "(extraction_confidence >= 0.0 AND extraction_confidence <= 1.0)",
        name="ck_claims_extraction_confidence_range",
    ),
)

claim_groups = Table(
    "claim_groups",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("canonical_key", Text, nullable=False, unique=True),
    Column("name", Text),
    Column("canonical_statement", Text, nullable=False),
    Column("subject", Text),
    Column("predicate", Text),
    Column("qualifiers", JSON, nullable=False),
    Column("temporal_scope", Text),
    Column("created_at", String(64), nullable=False),
    Column("created_by_stage_run_id", String(128), ForeignKey("stage_runs.id")),
)

claim_group_members = Table(
    "claim_group_members",
    metadata,
    Column("claim_group_id", String(128), ForeignKey("claim_groups.id"), primary_key=True),
    Column("claim_id", String(128), ForeignKey("claims.id"), primary_key=True),
)

evidence_links = Table(
    "evidence_links",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("evidence_id", String(128), ForeignKey("evidence.id"), nullable=False),
    Column("claim_id", String(128), ForeignKey("claims.id"), nullable=False),
    Column("relation_type", String(32), nullable=False),
    Column("rationale", Text),
    Column("created_at", String(64), nullable=False),
    Column("created_by_stage_run_id", String(128), ForeignKey("stage_runs.id")),
)

contradictions = Table(
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
    Column("created_by_stage_run_id", String(128), ForeignKey("stage_runs.id")),
)

resolved_claims = Table(
    "resolved_claims",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("claim_group_id", String(128), ForeignKey("claim_groups.id"), nullable=False),
    Column("canonical_statement", Text, nullable=False),
    Column("status", String(64), nullable=False),
    Column("confidence", Float),
    Column("resolution_reason", Text),
    Column("validity", Text),
    Column("resolution_decision_id", String(128), ForeignKey("resolution_decisions.id")),
    Column("confidence_assessment_id", String(128), ForeignKey("confidence_assessments.id")),
    Column("created_at", String(64), nullable=False),
    Column("created_by_stage_run_id", String(128), ForeignKey("stage_runs.id")),
    CheckConstraint(
        "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
        name="ck_resolved_claims_confidence_range",
    ),
)

knowledge_atoms = Table(
    "knowledge_atoms",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("resolved_claim_id", String(128), ForeignKey("resolved_claims.id"), nullable=False),
    Column("subject", Text),
    Column("predicate", Text),
    Column("object", Text),
    Column("statement", Text, nullable=False),
    Column("confidence", Float),
    Column("status", String(32), nullable=False),
    Column("validity", Text),
    Column("qualifiers", JSON, nullable=False),
    Column("created_at", String(64), nullable=False),
    Column("created_by_stage_run_id", String(128), ForeignKey("stage_runs.id")),
    CheckConstraint(
        "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
        name="ck_knowledge_atoms_confidence_range",
    ),
)

source_dependencies = Table(
    "source_dependencies",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("source_id", String(128), ForeignKey("sources.id"), nullable=False),
    Column("parent_source_id", String(128), ForeignKey("sources.id"), nullable=False),
    Column("relation_type", String(64), nullable=False),
    Column("dependency_group", String(128)),
    Column("independence_score", Float),
    Column("reason", Text),
    Column("signals", JSON, nullable=False),
    Column("created_at", String(64)),
    Column("created_by_stage_run_id", String(128), ForeignKey("stage_runs.id")),
    CheckConstraint(
        "independence_score IS NULL OR (independence_score >= 0.0 AND independence_score <= 1.0)",
        name="ck_source_dependencies_independence_score_range",
    ),
)

resolution_decisions = Table(
    "resolution_decisions",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("claim_group_id", String(128), ForeignKey("claim_groups.id"), nullable=False),
    Column("canonical_statement", Text, nullable=False),
    Column("status", String(64), nullable=False),
    Column("resolution_reason", Text, nullable=False),
    Column("validity", Text),
    Column("created_at", String(64), nullable=False),
    Column("created_by_stage_run_id", String(128), ForeignKey("stage_runs.id")),
)

resolution_claim_inputs = Table(
    "resolution_claim_inputs",
    metadata,
    Column("id", String(128), primary_key=True),
    Column(
        "resolution_decision_id",
        String(128),
        ForeignKey("resolution_decisions.id"),
        nullable=False,
    ),
    Column("claim_id", String(128), ForeignKey("claims.id"), nullable=False),
    Column("role", String(32), nullable=False),
    Column("reason", Text),
    Column("created_at", String(64), nullable=False),
    Column("created_by_stage_run_id", String(128), ForeignKey("stage_runs.id")),
    UniqueConstraint(
        "resolution_decision_id",
        "claim_id",
        "role",
        name="uq_resolution_claim_inputs_decision_claim_role",
    ),
)

resolution_evidence_inputs = Table(
    "resolution_evidence_inputs",
    metadata,
    Column("id", String(128), primary_key=True),
    Column(
        "resolution_decision_id",
        String(128),
        ForeignKey("resolution_decisions.id"),
        nullable=False,
    ),
    Column("evidence_id", String(128), ForeignKey("evidence.id"), nullable=False),
    Column("role", String(32), nullable=False),
    Column("reason", Text),
    Column("created_at", String(64), nullable=False),
    Column("created_by_stage_run_id", String(128), ForeignKey("stage_runs.id")),
    UniqueConstraint(
        "resolution_decision_id",
        "evidence_id",
        "role",
        name="uq_resolution_evidence_inputs_decision_evidence_role",
    ),
)

confidence_assessments = Table(
    "confidence_assessments",
    metadata,
    Column("id", String(128), primary_key=True),
    Column(
        "resolution_decision_id",
        String(128),
        ForeignKey("resolution_decisions.id"),
        nullable=False,
    ),
    Column("policy_version", String(128), nullable=False),
    Column("source_quality", Float, nullable=False),
    Column("evidence_directness", Float, nullable=False),
    Column("source_independence", Float, nullable=False),
    Column("agreement", Float, nullable=False),
    Column("freshness", Float, nullable=False),
    Column("extraction_confidence", Float, nullable=False),
    Column("contradiction_penalty", Float, nullable=False),
    Column("publish_cap", Float),
    Column("evidence_floor_met", Boolean, nullable=False),
    Column("score", Float, nullable=False),
    Column("reasons", JSON, nullable=False),
    Column("created_at", String(64), nullable=False),
    Column("created_by_stage_run_id", String(128), ForeignKey("stage_runs.id")),
    CheckConstraint(
        "source_quality >= 0.0 AND source_quality <= 1.0",
        name="ck_confidence_assessments_source_quality_range",
    ),
    CheckConstraint(
        "evidence_directness >= 0.0 AND evidence_directness <= 1.0",
        name="ck_confidence_assessments_evidence_directness_range",
    ),
    CheckConstraint(
        "source_independence >= 0.0 AND source_independence <= 1.0",
        name="ck_confidence_assessments_source_independence_range",
    ),
    CheckConstraint(
        "agreement >= 0.0 AND agreement <= 1.0",
        name="ck_confidence_assessments_agreement_range",
    ),
    CheckConstraint(
        "freshness >= 0.0 AND freshness <= 1.0",
        name="ck_confidence_assessments_freshness_range",
    ),
    CheckConstraint(
        "extraction_confidence >= 0.0 AND extraction_confidence <= 1.0",
        name="ck_confidence_assessments_extraction_confidence_range",
    ),
    CheckConstraint(
        "contradiction_penalty >= 0.0 AND contradiction_penalty <= 1.0",
        name="ck_confidence_assessments_contradiction_penalty_range",
    ),
    CheckConstraint(
        "publish_cap IS NULL OR (publish_cap >= 0.0 AND publish_cap <= 1.0)",
        name="ck_confidence_assessments_publish_cap_range",
    ),
    CheckConstraint(
        "score >= 0.0 AND score <= 1.0",
        name="ck_confidence_assessments_score_range",
    ),
)

human_overrides = Table(
    "human_overrides",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("entity_type", String(64), nullable=False),
    Column("entity_id", String(128), nullable=False),
    Column("action", String(64), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("created_at", String(64), nullable=False),
)

Index("ix_source_snapshots_source_id", source_snapshots.c.source_id)
Index("ix_evidence_snapshot_id", evidence.c.snapshot_id)
Index("ix_evidence_links_claim_id", evidence_links.c.claim_id)
Index("ix_evidence_links_evidence_id", evidence_links.c.evidence_id)
Index("ix_stage_runs_pipeline_run_id", stage_runs.c.pipeline_run_id)
Index("ix_claims_statement", claims.c.statement)
Index("ix_source_snapshots_created_by_stage_run_id", source_snapshots.c.created_by_stage_run_id)
Index("ix_evidence_created_by_stage_run_id", evidence.c.created_by_stage_run_id)
Index("ix_claims_created_by_stage_run_id", claims.c.created_by_stage_run_id)
Index("ix_claim_groups_created_by_stage_run_id", claim_groups.c.created_by_stage_run_id)
Index("ix_evidence_links_created_by_stage_run_id", evidence_links.c.created_by_stage_run_id)
Index("ix_contradictions_created_by_stage_run_id", contradictions.c.created_by_stage_run_id)
Index("ix_resolved_claims_created_by_stage_run_id", resolved_claims.c.created_by_stage_run_id)
Index("ix_knowledge_atoms_created_by_stage_run_id", knowledge_atoms.c.created_by_stage_run_id)
Index(
    "ix_source_dependencies_created_by_stage_run_id",
    source_dependencies.c.created_by_stage_run_id,
)
Index("ix_resolution_decisions_claim_group_id", resolution_decisions.c.claim_group_id)
Index(
    "ix_resolution_decisions_created_by_stage_run_id",
    resolution_decisions.c.created_by_stage_run_id,
)
Index(
    "ix_resolution_claim_inputs_resolution_decision_id",
    resolution_claim_inputs.c.resolution_decision_id,
)
Index("ix_resolution_claim_inputs_claim_id", resolution_claim_inputs.c.claim_id)
Index(
    "ix_resolution_claim_inputs_created_by_stage_run_id",
    resolution_claim_inputs.c.created_by_stage_run_id,
)
Index(
    "ix_resolution_evidence_inputs_resolution_decision_id",
    resolution_evidence_inputs.c.resolution_decision_id,
)
Index("ix_resolution_evidence_inputs_evidence_id", resolution_evidence_inputs.c.evidence_id)
Index(
    "ix_resolution_evidence_inputs_created_by_stage_run_id",
    resolution_evidence_inputs.c.created_by_stage_run_id,
)
Index(
    "ix_confidence_assessments_resolution_decision_id",
    confidence_assessments.c.resolution_decision_id,
)
Index(
    "ix_confidence_assessments_created_by_stage_run_id",
    confidence_assessments.c.created_by_stage_run_id,
)
Index("ix_resolved_claims_resolution_decision_id", resolved_claims.c.resolution_decision_id)
Index(
    "ix_resolved_claims_confidence_assessment_id",
    resolved_claims.c.confidence_assessment_id,
)
Index("ix_source_dependencies_source_id", source_dependencies.c.source_id)
Index("ix_source_dependencies_parent_source_id", source_dependencies.c.parent_source_id)
Index("ix_source_dependencies_dependency_group", source_dependencies.c.dependency_group)
