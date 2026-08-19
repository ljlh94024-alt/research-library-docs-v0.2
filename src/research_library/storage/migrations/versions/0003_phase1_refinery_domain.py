"""Add the Phase 1A Refinery domain foundation."""

import sqlalchemy as sa
from alembic import op

revision = "0003_phase1_refinery_domain"
down_revision = "0002_phase0_hardening"
branch_labels = None
depends_on = None


_NEW_INDEXES = (
    (
        "ix_claim_group_members_created_by_stage_run_id",
        "claim_group_members",
        "created_by_stage_run_id",
    ),
    ("ix_resolution_decisions_claim_group_id", "resolution_decisions", "claim_group_id"),
    (
        "ix_resolution_decisions_created_by_stage_run_id",
        "resolution_decisions",
        "created_by_stage_run_id",
    ),
    (
        "ix_resolution_claim_inputs_resolution_decision_id",
        "resolution_claim_inputs",
        "resolution_decision_id",
    ),
    ("ix_resolution_claim_inputs_claim_id", "resolution_claim_inputs", "claim_id"),
    (
        "ix_resolution_claim_inputs_created_by_stage_run_id",
        "resolution_claim_inputs",
        "created_by_stage_run_id",
    ),
    (
        "ix_resolution_evidence_inputs_resolution_decision_id",
        "resolution_evidence_inputs",
        "resolution_decision_id",
    ),
    ("ix_resolution_evidence_inputs_evidence_id", "resolution_evidence_inputs", "evidence_id"),
    (
        "ix_resolution_evidence_inputs_created_by_stage_run_id",
        "resolution_evidence_inputs",
        "created_by_stage_run_id",
    ),
    (
        "ix_confidence_assessments_resolution_decision_id",
        "confidence_assessments",
        "resolution_decision_id",
    ),
    (
        "ix_confidence_assessments_created_by_stage_run_id",
        "confidence_assessments",
        "created_by_stage_run_id",
    ),
    ("ix_resolved_claims_resolution_decision_id", "resolved_claims", "resolution_decision_id"),
    (
        "ix_resolved_claims_confidence_assessment_id",
        "resolved_claims",
        "confidence_assessment_id",
    ),
    ("ix_source_dependencies_source_id", "source_dependencies", "source_id"),
    ("ix_source_dependencies_parent_source_id", "source_dependencies", "parent_source_id"),
    ("ix_source_dependencies_dependency_group", "source_dependencies", "dependency_group"),
)


def _create_indexes() -> None:
    for name, table, column in _NEW_INDEXES:
        op.create_index(name, table, [column])


def _drop_indexes() -> None:
    for name, table, _column in reversed(_NEW_INDEXES):
        op.drop_index(name, table_name=table)


def upgrade() -> None:
    op.create_table(
        "resolution_decisions",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("claim_group_id", sa.String(128), nullable=False),
        sa.Column("canonical_statement", sa.Text, nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("resolution_reason", sa.Text, nullable=False),
        sa.Column("validity", sa.Text),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("created_by_stage_run_id", sa.String(128)),
        sa.ForeignKeyConstraint(["claim_group_id"], ["claim_groups.id"]),
        sa.ForeignKeyConstraint(["created_by_stage_run_id"], ["stage_runs.id"]),
    )
    op.create_table(
        "resolution_claim_inputs",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("resolution_decision_id", sa.String(128), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("created_by_stage_run_id", sa.String(128)),
        sa.ForeignKeyConstraint(["resolution_decision_id"], ["resolution_decisions.id"]),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["created_by_stage_run_id"], ["stage_runs.id"]),
        sa.UniqueConstraint(
            "resolution_decision_id",
            "claim_id",
            "role",
            name="uq_resolution_claim_inputs_decision_claim_role",
        ),
    )
    op.create_table(
        "resolution_evidence_inputs",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("resolution_decision_id", sa.String(128), nullable=False),
        sa.Column("evidence_id", sa.String(128), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("created_by_stage_run_id", sa.String(128)),
        sa.ForeignKeyConstraint(["resolution_decision_id"], ["resolution_decisions.id"]),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence.id"]),
        sa.ForeignKeyConstraint(["created_by_stage_run_id"], ["stage_runs.id"]),
        sa.UniqueConstraint(
            "resolution_decision_id",
            "evidence_id",
            "role",
            name="uq_resolution_evidence_inputs_decision_evidence_role",
        ),
    )
    op.create_table(
        "confidence_assessments",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("resolution_decision_id", sa.String(128), nullable=False),
        sa.Column("policy_version", sa.String(128), nullable=False),
        sa.Column("source_quality", sa.Float, nullable=False),
        sa.Column("evidence_directness", sa.Float, nullable=False),
        sa.Column("source_independence", sa.Float, nullable=False),
        sa.Column("agreement", sa.Float, nullable=False),
        sa.Column("freshness", sa.Float, nullable=False),
        sa.Column("extraction_confidence", sa.Float, nullable=False),
        sa.Column("contradiction_penalty", sa.Float, nullable=False),
        sa.Column("publish_cap", sa.Float),
        sa.Column("evidence_floor_met", sa.Boolean, nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("reasons", sa.JSON, nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("created_by_stage_run_id", sa.String(128)),
        sa.ForeignKeyConstraint(["resolution_decision_id"], ["resolution_decisions.id"]),
        sa.ForeignKeyConstraint(["created_by_stage_run_id"], ["stage_runs.id"]),
        sa.CheckConstraint(
            "source_quality >= 0.0 AND source_quality <= 1.0",
            name="ck_confidence_assessments_source_quality_range",
        ),
        sa.CheckConstraint(
            "evidence_directness >= 0.0 AND evidence_directness <= 1.0",
            name="ck_confidence_assessments_evidence_directness_range",
        ),
        sa.CheckConstraint(
            "source_independence >= 0.0 AND source_independence <= 1.0",
            name="ck_confidence_assessments_source_independence_range",
        ),
        sa.CheckConstraint(
            "agreement >= 0.0 AND agreement <= 1.0",
            name="ck_confidence_assessments_agreement_range",
        ),
        sa.CheckConstraint(
            "freshness >= 0.0 AND freshness <= 1.0",
            name="ck_confidence_assessments_freshness_range",
        ),
        sa.CheckConstraint(
            "extraction_confidence >= 0.0 AND extraction_confidence <= 1.0",
            name="ck_confidence_assessments_extraction_confidence_range",
        ),
        sa.CheckConstraint(
            "contradiction_penalty >= 0.0 AND contradiction_penalty <= 1.0",
            name="ck_confidence_assessments_contradiction_penalty_range",
        ),
        sa.CheckConstraint(
            "publish_cap IS NULL OR (publish_cap >= 0.0 AND publish_cap <= 1.0)",
            name="ck_confidence_assessments_publish_cap_range",
        ),
        sa.CheckConstraint(
            "score >= 0.0 AND score <= 1.0",
            name="ck_confidence_assessments_score_range",
        ),
        sa.CheckConstraint(
            "evidence_floor_met IN (0, 1)",
            name="ck_confidence_assessments_evidence_floor_met_bool",
        ),
    )

    with op.batch_alter_table("claim_groups", recreate="always") as batch:
        batch.add_column(sa.Column("canonical_statement", sa.Text, nullable=True))
        batch.add_column(sa.Column("subject", sa.Text))
        batch.add_column(sa.Column("predicate", sa.Text))
        batch.add_column(sa.Column("qualifiers", sa.JSON, nullable=True))
        batch.add_column(sa.Column("temporal_scope", sa.Text))
    op.execute(
        sa.text(
            "UPDATE claim_groups SET canonical_statement = COALESCE(name, canonical_key), "
            "qualifiers = '{}' WHERE canonical_statement IS NULL"
        )
    )
    with op.batch_alter_table("claim_groups", recreate="always") as batch:
        batch.alter_column("canonical_statement", existing_type=sa.Text(), nullable=False)
        batch.alter_column("qualifiers", existing_type=sa.JSON(), nullable=False)

    with op.batch_alter_table("source_dependencies", recreate="always") as batch:
        batch.add_column(sa.Column("relation_type", sa.String(64), nullable=True))
        batch.add_column(sa.Column("signals", sa.JSON, nullable=True))
        batch.add_column(sa.Column("created_at", sa.String(64), nullable=True))
    op.execute(
        sa.text(
            "UPDATE source_dependencies SET relation_type = 'possibly_dependent', "
            "signals = '{}' WHERE relation_type IS NULL"
        )
    )
    with op.batch_alter_table("source_dependencies", recreate="always") as batch:
        batch.alter_column("relation_type", existing_type=sa.String(64), nullable=False)
        batch.alter_column("signals", existing_type=sa.JSON(), nullable=False)

    with op.batch_alter_table("claim_group_members", recreate="always") as batch:
        batch.add_column(sa.Column("created_at", sa.String(64), nullable=True))
        batch.add_column(
            sa.Column(
                "created_by_stage_run_id",
                sa.String(128),
                sa.ForeignKey(
                    "stage_runs.id", name="fk_claim_group_members_created_by_stage_run_id"
                ),
                nullable=True,
            )
        )

    with op.batch_alter_table("resolved_claims", recreate="always") as batch:
        batch.add_column(sa.Column("resolution_decision_id", sa.String(128)))
        batch.add_column(sa.Column("confidence_assessment_id", sa.String(128)))
        batch.create_foreign_key(
            "fk_resolved_claims_resolution_decision_id",
            "resolution_decisions",
            ["resolution_decision_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_resolved_claims_confidence_assessment_id",
            "confidence_assessments",
            ["confidence_assessment_id"],
            ["id"],
        )

    with op.batch_alter_table("knowledge_atoms", recreate="always") as batch:
        batch.add_column(sa.Column("subject", sa.Text))
        batch.add_column(sa.Column("predicate", sa.Text))
        batch.add_column(sa.Column("object", sa.Text))
        batch.add_column(sa.Column("status", sa.String(32), nullable=True))
        batch.add_column(sa.Column("validity", sa.Text))
    op.execute(sa.text("UPDATE knowledge_atoms SET status = 'withheld' WHERE status IS NULL"))
    with op.batch_alter_table("knowledge_atoms", recreate="always") as batch:
        batch.alter_column("status", existing_type=sa.String(32), nullable=False)

    _create_indexes()


def downgrade() -> None:
    _drop_indexes()

    with op.batch_alter_table("claim_group_members", recreate="always") as batch:
        batch.drop_column("created_by_stage_run_id")
        batch.drop_column("created_at")

    with op.batch_alter_table("resolved_claims", recreate="always") as batch:
        batch.drop_constraint("fk_resolved_claims_confidence_assessment_id", type_="foreignkey")
        batch.drop_constraint("fk_resolved_claims_resolution_decision_id", type_="foreignkey")
        batch.drop_column("confidence_assessment_id")
        batch.drop_column("resolution_decision_id")

    with op.batch_alter_table("knowledge_atoms", recreate="always") as batch:
        batch.drop_column("validity")
        batch.drop_column("status")
        batch.drop_column("object")
        batch.drop_column("predicate")
        batch.drop_column("subject")

    with op.batch_alter_table("source_dependencies", recreate="always") as batch:
        batch.drop_column("created_at")
        batch.drop_column("signals")
        batch.drop_column("relation_type")

    with op.batch_alter_table("claim_groups", recreate="always") as batch:
        batch.drop_column("temporal_scope")
        batch.drop_column("qualifiers")
        batch.drop_column("predicate")
        batch.drop_column("subject")
        batch.drop_column("canonical_statement")

    op.drop_table("confidence_assessments")
    op.drop_table("resolution_evidence_inputs")
    op.drop_table("resolution_claim_inputs")
    op.drop_table("resolution_decisions")
