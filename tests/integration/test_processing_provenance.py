from pathlib import Path

from sqlalchemy import create_engine

from research_library.domain import (
    Claim,
    ClaimGroup,
    Evidence,
    EvidenceLink,
    KnowledgeAtom,
    PipelineRun,
    ResolvedClaim,
    Source,
    StageRun,
)
from research_library.storage import ProcessingGap, StorageIntegrityError


def _build_processed_atom(repository, *, snapshot_stage="processing-stage"):
    pipeline = repository.save_pipeline_run(PipelineRun(id="processing-pipeline"))
    stage = repository.save_stage_run(
        StageRun(id="processing-stage", pipeline_run_id=pipeline.id, stage_name="fixture")
    )
    source = repository.save_source(Source(id="processing-source", canonical_uri="https://example.test"))
    snapshot = repository.create_snapshot(
        source.id,
        b"processed content",
        snapshot_id="processing-snapshot",
        created_by_stage_run_id=snapshot_stage,
    )
    evidence = repository.save_evidence(
        Evidence(
            id="processing-evidence",
            snapshot_id=snapshot.id,
            text="processed quote",
            created_by_stage_run_id=stage.id,
        )
    )
    claim = repository.save_claim(
        Claim(id="processing-claim", statement="processed fact", created_by_stage_run_id=stage.id)
    )
    group = repository.save_claim_group(
        ClaimGroup(
            id="processing-group",
            canonical_key="processed-fact",
            created_by_stage_run_id=stage.id,
        )
    )
    repository.add_claim_to_group(group.id, claim.id)
    link = repository.save_evidence_link(
        EvidenceLink(
            id="processing-link",
            evidence_id=evidence.id,
            claim_id=claim.id,
            created_by_stage_run_id=stage.id,
        )
    )
    resolved = repository.save_resolved_claim(
        ResolvedClaim(
            id="processing-resolved",
            claim_group_id=group.id,
            canonical_statement="processed fact",
            created_by_stage_run_id=stage.id,
        )
    )
    atom = repository.save_knowledge_atom(
        KnowledgeAtom(
            id="processing-atom",
            resolved_claim_id=resolved.id,
            statement="processed fact",
            created_by_stage_run_id=stage.id,
        )
    )
    return atom, pipeline, stage, (snapshot, evidence, claim, group, link, resolved)


def test_processing_provenance_returns_stage_and_pipeline_for_full_chain(repository) -> None:
    atom, pipeline, stage, entities = _build_processed_atom(repository)
    provenance = repository.get_processing_provenance(atom.id)
    assert provenance.atom_id == atom.id
    assert [step.entity_type for step in provenance.steps] == [
        "source_snapshot",
        "evidence",
        "evidence_link",
        "claim",
        "claim_group",
        "resolved_claim",
        "knowledge_atom",
    ]
    assert all(step.stage_run.id == stage.id for step in provenance.steps)
    assert all(step.pipeline_run.id == pipeline.id for step in provenance.steps)
    assert {step.entity_id for step in provenance.steps} == {
        item.id for item in (*entities, atom)
    }


def test_processing_provenance_fails_loudly_on_broken_stage_lineage(repository) -> None:
    atom, _, _, _ = _build_processed_atom(repository)
    database_path = Path(repository.db_path)
    corrupting_engine = create_engine(f"sqlite+pysqlite:///{database_path.resolve().as_posix()}")
    raw = corrupting_engine.raw_connection()
    try:
        raw.execute("PRAGMA foreign_keys=OFF")
        raw.execute(
            "UPDATE knowledge_atoms SET created_by_stage_run_id = 'missing-stage' WHERE id = ?",
            (atom.id,),
        )
        raw.commit()
    finally:
        raw.close()
        corrupting_engine.dispose()
    try:
        repository.get_processing_provenance(atom.id)
    except StorageIntegrityError as exc:
        assert "missing stage run" in str(exc)
    else:
        raise AssertionError("broken processing lineage was not rejected")


def test_processing_provenance_allows_valid_unattributed_imports(repository) -> None:
    atom, _, stage, _ = _build_processed_atom(repository, snapshot_stage=None)
    provenance = repository.get_processing_provenance(atom.id)
    assert not provenance.is_complete
    assert provenance.gaps == (
        ProcessingGap(
            entity_type="source_snapshot",
            entity_id="processing-snapshot",
            reason="not_recorded",
        ),
    )
    assert all(step.stage_run.id == stage.id for step in provenance.steps)
