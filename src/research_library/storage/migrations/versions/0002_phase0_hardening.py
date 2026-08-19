"""Harden the Phase 0 schema without rewriting the historical revision."""

import sqlalchemy as sa
from alembic import op

revision = "0002_phase0_hardening"
down_revision = "0001_phase0"
branch_labels = None
depends_on = None

_OLD_INDEXES = (
    ("ix_source_snapshots_source_id", "source_snapshots"),
    ("ix_evidence_snapshot_id", "evidence"),
    ("ix_evidence_links_claim_id", "evidence_links"),
    ("ix_evidence_links_evidence_id", "evidence_links"),
    ("ix_stage_runs_pipeline_run_id", "stage_runs"),
    ("ix_claims_statement", "claims"),
)

_NEW_INDEXES = (
    ("ix_source_snapshots_created_by_stage_run_id", "source_snapshots"),
    ("ix_evidence_created_by_stage_run_id", "evidence"),
    ("ix_claims_created_by_stage_run_id", "claims"),
    ("ix_claim_groups_created_by_stage_run_id", "claim_groups"),
    ("ix_evidence_links_created_by_stage_run_id", "evidence_links"),
    ("ix_contradictions_created_by_stage_run_id", "contradictions"),
    ("ix_resolved_claims_created_by_stage_run_id", "resolved_claims"),
    ("ix_knowledge_atoms_created_by_stage_run_id", "knowledge_atoms"),
    ("ix_source_dependencies_created_by_stage_run_id", "source_dependencies"),
)


def _drop_indexes(indexes: tuple[tuple[str, str], ...]) -> None:
    for name, table in indexes:
        op.drop_index(name, table_name=table)


def _create_indexes() -> None:
    for name, table in (*_OLD_INDEXES, *_NEW_INDEXES):
        column = name.removeprefix("ix_")
        if table == "source_snapshots" and name == "ix_source_snapshots_source_id":
            column = "source_id"
        elif table == "evidence" and name == "ix_evidence_snapshot_id":
            column = "snapshot_id"
        elif table == "evidence_links" and name == "ix_evidence_links_claim_id":
            column = "claim_id"
        elif table == "evidence_links" and name == "ix_evidence_links_evidence_id":
            column = "evidence_id"
        elif table == "stage_runs":
            column = "pipeline_run_id"
        elif table == "claims" and name == "ix_claims_statement":
            column = "statement"
        elif name.endswith("_created_by_stage_run_id"):
            column = "created_by_stage_run_id"
        op.create_index(name, table, [column])


def upgrade() -> None:
    _drop_indexes(_OLD_INDEXES)

    with op.batch_alter_table("source_snapshots", recreate="always") as batch:
        batch.create_foreign_key(
            "fk_source_snapshots_created_by_stage_run_id",
            "stage_runs",
            ["created_by_stage_run_id"],
            ["id"],
        )
    with op.batch_alter_table("evidence", recreate="always") as batch:
        batch.create_foreign_key(
            "fk_evidence_created_by_stage_run_id",
            "stage_runs",
            ["created_by_stage_run_id"],
            ["id"],
        )
    with op.batch_alter_table("claims", recreate="always") as batch:
        batch.alter_column(
            "extraction_confidence",
            existing_type=sa.String(32),
            type_=sa.Float(),
        )
        batch.create_foreign_key(
            "fk_claims_created_by_stage_run_id",
            "stage_runs",
            ["created_by_stage_run_id"],
            ["id"],
        )
        batch.create_check_constraint(
            "ck_claims_extraction_confidence_range",
            "extraction_confidence IS NULL OR "
            "(extraction_confidence >= 0.0 AND extraction_confidence <= 1.0)",
        )
    with op.batch_alter_table("claim_groups", recreate="always") as batch:
        batch.add_column(sa.Column("created_by_stage_run_id", sa.String(128)))
        batch.create_foreign_key(
            "fk_claim_groups_created_by_stage_run_id",
            "stage_runs",
            ["created_by_stage_run_id"],
            ["id"],
        )
    with op.batch_alter_table("evidence_links", recreate="always") as batch:
        batch.create_foreign_key(
            "fk_evidence_links_created_by_stage_run_id",
            "stage_runs",
            ["created_by_stage_run_id"],
            ["id"],
        )
    with op.batch_alter_table("contradictions", recreate="always") as batch:
        batch.add_column(sa.Column("created_by_stage_run_id", sa.String(128)))
        batch.create_foreign_key(
            "fk_contradictions_created_by_stage_run_id",
            "stage_runs",
            ["created_by_stage_run_id"],
            ["id"],
        )
    with op.batch_alter_table("resolved_claims", recreate="always") as batch:
        batch.alter_column("confidence", existing_type=sa.String(32), type_=sa.Float())
        batch.create_foreign_key(
            "fk_resolved_claims_created_by_stage_run_id",
            "stage_runs",
            ["created_by_stage_run_id"],
            ["id"],
        )
        batch.create_check_constraint(
            "ck_resolved_claims_confidence_range",
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
        )
    with op.batch_alter_table("knowledge_atoms", recreate="always") as batch:
        batch.alter_column("confidence", existing_type=sa.String(32), type_=sa.Float())
        batch.create_foreign_key(
            "fk_knowledge_atoms_created_by_stage_run_id",
            "stage_runs",
            ["created_by_stage_run_id"],
            ["id"],
        )
        batch.create_check_constraint(
            "ck_knowledge_atoms_confidence_range",
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
        )
    with op.batch_alter_table("source_dependencies", recreate="always") as batch:
        batch.alter_column(
            "independence_score",
            existing_type=sa.String(32),
            type_=sa.Float(),
        )
        batch.add_column(sa.Column("created_by_stage_run_id", sa.String(128)))
        batch.create_foreign_key(
            "fk_source_dependencies_created_by_stage_run_id",
            "stage_runs",
            ["created_by_stage_run_id"],
            ["id"],
        )
        batch.create_check_constraint(
            "ck_source_dependencies_independence_score_range",
            "independence_score IS NULL OR "
            "(independence_score >= 0.0 AND independence_score <= 1.0)",
        )

    _create_indexes()


def downgrade() -> None:
    _drop_indexes((*_OLD_INDEXES, *_NEW_INDEXES))

    with op.batch_alter_table("source_dependencies", recreate="always") as batch:
        batch.drop_constraint(
            "ck_source_dependencies_independence_score_range", type_="check"
        )
        batch.drop_constraint("fk_source_dependencies_created_by_stage_run_id", type_="foreignkey")
        batch.alter_column(
            "independence_score",
            existing_type=sa.Float(),
            type_=sa.String(32),
        )
        batch.drop_column("created_by_stage_run_id")
    with op.batch_alter_table("knowledge_atoms", recreate="always") as batch:
        batch.drop_constraint("ck_knowledge_atoms_confidence_range", type_="check")
        batch.drop_constraint("fk_knowledge_atoms_created_by_stage_run_id", type_="foreignkey")
        batch.alter_column("confidence", existing_type=sa.Float(), type_=sa.String(32))
    with op.batch_alter_table("resolved_claims", recreate="always") as batch:
        batch.drop_constraint("ck_resolved_claims_confidence_range", type_="check")
        batch.drop_constraint("fk_resolved_claims_created_by_stage_run_id", type_="foreignkey")
        batch.alter_column("confidence", existing_type=sa.Float(), type_=sa.String(32))
    with op.batch_alter_table("contradictions", recreate="always") as batch:
        batch.drop_constraint("fk_contradictions_created_by_stage_run_id", type_="foreignkey")
        batch.drop_column("created_by_stage_run_id")
    with op.batch_alter_table("evidence_links", recreate="always") as batch:
        batch.drop_constraint("fk_evidence_links_created_by_stage_run_id", type_="foreignkey")
    with op.batch_alter_table("claim_groups", recreate="always") as batch:
        batch.drop_constraint("fk_claim_groups_created_by_stage_run_id", type_="foreignkey")
        batch.drop_column("created_by_stage_run_id")
    with op.batch_alter_table("claims", recreate="always") as batch:
        batch.drop_constraint("ck_claims_extraction_confidence_range", type_="check")
        batch.drop_constraint("fk_claims_created_by_stage_run_id", type_="foreignkey")
        batch.alter_column(
            "extraction_confidence",
            existing_type=sa.Float(),
            type_=sa.String(32),
        )
    with op.batch_alter_table("evidence", recreate="always") as batch:
        batch.drop_constraint("fk_evidence_created_by_stage_run_id", type_="foreignkey")
    with op.batch_alter_table("source_snapshots", recreate="always") as batch:
        batch.drop_constraint("fk_source_snapshots_created_by_stage_run_id", type_="foreignkey")

    for name, table in _OLD_INDEXES:
        column = name.removeprefix("ix_")
        if table == "source_snapshots":
            column = "source_id"
        elif table == "evidence":
            column = "snapshot_id"
        elif table == "evidence_links":
            column = column.removeprefix("evidence_links_")
        elif table == "stage_runs":
            column = "pipeline_run_id"
        elif table == "claims":
            column = "statement"
        op.create_index(name, table, [column])
