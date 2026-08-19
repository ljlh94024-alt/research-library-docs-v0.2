import pytest
from sqlalchemy.exc import IntegrityError

from research_library.domain import ClaimGroup, ResolutionDecision, Source
from research_library.storage.schema import confidence_assessments


def test_confidence_assessment_database_checks_reject_out_of_range_values(repository) -> None:
    group = repository.save_claim_group(
        ClaimGroup(id="constraint-group", canonical_key="constraint", canonical_statement="fact")
    )
    decision = repository.save_resolution_decision(
        ResolutionDecision(
            id="constraint-decision",
            claim_group_id=group.id,
            canonical_statement="fact",
            resolution_reason="constraint fixture",
        )
    )
    base = {
        "resolution_decision_id": decision.id,
        "policy_version": "test",
        "source_quality": 0.5,
        "evidence_directness": 0.5,
        "source_independence": 0.5,
        "agreement": 0.5,
        "freshness": 0.5,
        "extraction_confidence": 0.5,
        "contradiction_penalty": 0.0,
        "publish_cap": None,
        "evidence_floor_met": True,
        "score": 0.5,
        "reasons": {"fixture": ["test"]},
        "created_at": "2026-08-19T00:00:00+00:00",
    }
    cases = (
        ("source_quality", -0.01),
        ("evidence_directness", 1.01),
        ("source_independence", -0.01),
        ("agreement", 1.01),
        ("freshness", -0.01),
        ("extraction_confidence", 1.01),
        ("contradiction_penalty", -0.01),
        ("publish_cap", -0.01),
        ("score", 1.01),
    )
    for number, (field, value) in enumerate(cases):
        values = {**base, "id": f"constraint-assessment-{number}", field: value}
        with pytest.raises(IntegrityError):
            with repository.engine.begin() as connection:
                connection.execute(confidence_assessments.insert().values(**values))


def test_source_dependency_database_keeps_fk_integrity(repository) -> None:
    source = repository.save_source(Source(id="constraint-source", canonical_uri="https://source"))
    with pytest.raises(IntegrityError):
        with repository.engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO source_dependencies "
                "(id, source_id, parent_source_id, relation_type, signals) "
                "VALUES (?, ?, ?, ?, ?)",
                ("bad-dependency", source.id, "missing-parent", "cites", "{}"),
            )
