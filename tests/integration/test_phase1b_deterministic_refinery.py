
import pytest

from research_library.domain import (
    Claim,
    Contradiction,
    ContradictionSeverity,
    ContradictionStatus,
    ContradictionType,
    EvidenceLink,
    EvidenceLinkType,
    KnowledgeAtomStatus,
    ResolutionInputRole,
    ResolvedClaimStatus,
    SourceDependency,
    SourceDependencyRelation,
)
from research_library.refinery import (
    CANONICAL_STAGE_NAMES,
    DETERMINISTIC_PIPELINE_VERSION,
    GOLDEN_FIXTURE_IDS,
    AtomPolicy,
    ConfidencePolicy,
    ContradictionPolicy,
    DeterministicRefinery,
    FixtureSemanticBackend,
    IndependencePolicy,
    ManifestIntegrityError,
    NormalizationPolicy,
    ResolutionPolicy,
    SemanticBackend,
    StageManifest,
    StageManifestStore,
)


def test_five_golden_fixtures_have_exact_frozen_results(repository) -> None:
    runner = DeterministicRefinery(repository, FixtureSemanticBackend())

    independent = runner.run("independent_support")
    assert independent.decisions[0].status is ResolvedClaimStatus.RESOLVED
    assert independent.assessments[0].evidence_floor_met is True
    assert independent.assessments[0].score >= 0.75
    assert independent.atoms[0].status is KnowledgeAtomStatus.ACTIVE

    repost = runner.run("multi_repost_same_origin")
    assert len(repost.dependencies) == 10
    assert repost.metrics["effective_independence_count"] == 1
    assert repost.decisions[0].status is ResolvedClaimStatus.RESOLVED
    assert repost.assessments[0].evidence_floor_met is False
    assert repost.assessments[0].score <= 0.65
    assert repost.atoms[0].status is KnowledgeAtomStatus.WITHHELD

    conflict = runner.run("direct_conflict")
    assert len(conflict.contradictions) == 1
    assert conflict.contradictions[0].type is ContradictionType.DIRECT
    assert conflict.decisions[0].status is ResolvedClaimStatus.CONFLICTING
    assert conflict.atoms[0].status is KnowledgeAtomStatus.WITHHELD

    qualified = runner.run("qualified_support")
    assert {item.relation_type for item in qualified.evidence_links} == {EvidenceLinkType.QUALIFIES}
    assert qualified.decisions[0].status is ResolvedClaimStatus.INSUFFICIENT_EVIDENCE
    assert qualified.evidence_inputs[0].role is ResolutionInputRole.QUALIFYING
    assert qualified.atoms[0].status is KnowledgeAtomStatus.WITHHELD

    assert set(GOLDEN_FIXTURE_IDS) == {
        "independent_support",
        "multi_repost_same_origin",
        "direct_conflict",
        "qualified_support",
        "snapshot_history",
    }


def test_snapshot_history_is_two_independent_runs(repository) -> None:
    runner = DeterministicRefinery(repository, FixtureSemanticBackend())

    old = runner.run("snapshot_history", snapshot_keys=("snapshot-old",))
    new = runner.run("snapshot_history", snapshot_keys=("snapshot-new",))

    assert old.pipeline_run.id != new.pipeline_run.id
    assert set(old.artifact_ids).isdisjoint(new.artifact_ids)
    assert old.semantic_signature != new.semantic_signature
    assert old.snapshots[0].id != new.snapshots[0].id
    assert repository.get_pipeline_run(old.pipeline_run.id) == old.pipeline_run
    assert repository.get_stage_run(old.stage_runs[0].id) == old.stage_runs[0]
    assert repository.get_evidence(old.evidences[0].id) == old.evidences[0]
    assert repository.get_resolved_claim(old.resolved_claims[0].id) == old.resolved_claims[0]
    assert repository.get_knowledge_atom(old.atoms[0].id) == old.atoms[0]
    assert repository.read_snapshot(old.snapshots[0].id) == b"The archive listed 7 entries in 2023."
    assert repository.read_snapshot(new.snapshots[0].id) == b"The archive listed 9 entries in 2025."
    assert len(repository.list_pipeline_runs()) == 2


def test_all_nine_stages_have_processing_provenance(repository) -> None:
    result = DeterministicRefinery(repository).run("independent_support")
    provenance = repository.get_processing_provenance(result.atoms[0].id)

    assert {item.stage_name for item in result.stage_runs} == set(CANONICAL_STAGE_NAMES)
    assert {step.stage_run.stage_name for step in provenance.steps}.issubset(
        set(CANONICAL_STAGE_NAMES)
    )
    assert all(step.pipeline_run.id == result.pipeline_run.id for step in provenance.steps)
    assert {gap.entity_type for gap in provenance.gaps} == {"source_snapshot"}
    assert result.snapshots[0].created_by_stage_run_id is None


def test_normalization_uses_persisted_claim_and_omits_object() -> None:
    left = Claim(
        id="left",
        statement="ignored",
        subject="  Café  ",
        predicate=" HAS VALUE ",
        object="one",
        qualifiers={" Region ": " EU "},
        temporal_scope=" 2025 ",
    )
    right = Claim(
        id="right",
        statement="ignored",
        subject="CAFE\u0301",
        predicate="has   value",
        object="two",
        qualifiers={"region": "eu"},
        temporal_scope="2025",
    )

    assert NormalizationPolicy.comparison_key(left) == NormalizationPolicy.comparison_key(right)
    assert NormalizationPolicy.signature(left) == NormalizationPolicy.signature(right)


def test_independence_uses_persisted_dependency_decisions() -> None:
    dependencies = (
        SourceDependency(
            id="dependency-repost",
            source_id="repost",
            parent_source_id="origin",
            relation_type=SourceDependencyRelation.REPOST_OF,
            dependency_group="origin-group",
            independence_score=0.0,
        ),
    )

    assert IndependencePolicy.count({"origin", "repost"}, dependencies) == 1
    assert IndependencePolicy.count({"origin", "independent"}, dependencies) == 2


def test_contradiction_policy_distinguishes_direct_and_temporal() -> None:
    common = {"statement": "value", "subject": "sample", "predicate": "value"}
    direct_left = Claim(id="a", object="10", **common)
    direct_right = Claim(id="b", object="20", **common)
    temporal = Claim(id="c", object="20", temporal_scope="2025", **common)

    assert ContradictionPolicy.classify(direct_left, direct_right) is ContradictionType.DIRECT
    assert ContradictionPolicy.classify(direct_left, temporal) is ContradictionType.TEMPORAL
    assert ContradictionPolicy.incompatible(direct_left, temporal) is False


def test_resolution_ranks_values_by_effective_support_units() -> None:
    claims = (
        Claim(id="claim-a", statement="a", subject="sample", predicate="value", object="10"),
        Claim(id="claim-b", statement="b", subject="sample", predicate="value", object="20"),
    )
    links = (
        EvidenceLink(id="link-a", evidence_id="evidence-a", claim_id="claim-a"),
        EvidenceLink(id="link-b", evidence_id="evidence-b", claim_id="claim-b"),
    )
    contradiction = Contradiction(
        id="contradiction",
        claim_a_id="claim-a",
        claim_b_id="claim-b",
        type=ContradictionType.DIRECT,
        severity=ContradictionSeverity.HIGH,
        reason="different values",
        status=ContradictionStatus.OPEN,
    )

    outcome = ResolutionPolicy.evaluate(
        claims,
        links,
        (contradiction,),
        lambda evidence_id: evidence_id,
        (),
    )
    assert outcome.status is ResolvedClaimStatus.CONFLICTING
    assert outcome.selected_value is None
    assert outcome.supported_values == ("10", "20")


def test_confidence_policy_uses_exact_weighted_formula() -> None:
    values = ConfidencePolicy.assess(
        status=ResolvedClaimStatus.RESOLVED,
        claims=(Claim(id="claim", statement="claim", extraction_confidence=0.8),),
        links=(EvidenceLink(id="link", evidence_id="evidence", claim_id="claim"),),
        source_quality=0.9,
        independent_support_units=2,
        agreement=1.0,
        freshness=0.6,
        contradictions=(),
    )

    expected = round(0.9 * 0.15 + 1.0 * 0.20 + 1.0 * 0.25 + 1.0 * 0.20 + 0.6 * 0.10 + 0.8 * 0.10, 6)
    assert values["score"] == expected
    assert values["evidence_floor_met"] is True
    assert values["publish_cap"] is None


def test_atom_policy_requires_resolution_floor_and_threshold() -> None:
    assert AtomPolicy.status(ResolvedClaimStatus.RESOLVED, True, 0.75) is KnowledgeAtomStatus.ACTIVE
    assert (
        AtomPolicy.status(ResolvedClaimStatus.RESOLVED, True, 0.749999)
        is KnowledgeAtomStatus.WITHHELD
    )
    assert (
        AtomPolicy.status(ResolvedClaimStatus.RESOLVED, False, 0.99) is KnowledgeAtomStatus.WITHHELD
    )
    assert (
        AtomPolicy.status(ResolvedClaimStatus.CONFLICTING, True, 0.99)
        is KnowledgeAtomStatus.WITHHELD
    )


def test_fixture_backend_implements_provider_neutral_protocol() -> None:
    backend = FixtureSemanticBackend()
    assert isinstance(backend, SemanticBackend)
    batch = backend.collect(
        "qualified_support",
        (
            backend.snapshot_id(
                "qualified_support", next(backend.iter_snapshots("qualified_support"))
            ),
        ),
    )
    assert batch.claims[0].candidate_id == "claim"
    assert batch.relations[0].relation_type is EvidenceLinkType.QUALIFIES


def test_manifest_store_roundtrip_missing_safe_path_and_tamper(tmp_path) -> None:
    store = StageManifestStore(tmp_path / "manifests")
    manifest = StageManifest("normalize", DETERMINISTIC_PIPELINE_VERSION, ("input",), ("output",))

    assert store.write(manifest) == manifest.ref
    assert store.read(manifest.ref) == manifest
    assert store.read(manifest.ref).as_dict() == store.read(manifest.ref).as_dict()
    with pytest.raises(ManifestIntegrityError):
        store.read("manifest:../escape")
    with pytest.raises(ManifestIntegrityError):
        store.read("manifest:" + "manifest-" + "0" * 64)
    path = store.root / f"{manifest.manifest_id}.json"
    path.write_text(
        path.read_text(encoding="utf-8").replace('"output"', '"tampered"'), encoding="utf-8"
    )
    with pytest.raises(ManifestIntegrityError):
        store.read(manifest.ref)


def test_artifacts_are_stable_for_recovery_and_new_for_new_run(repository) -> None:
    runner = DeterministicRefinery(repository)
    first = runner.run("independent_support")
    recovered = runner.run("independent_support", recovery_key="recovery-1")
    recovered_again = runner.run("independent_support", recovery_key="recovery-1")
    new_run = runner.run("independent_support")

    assert recovered.pipeline_run.id == recovered_again.pipeline_run.id
    assert recovered.artifact_ids == recovered_again.artifact_ids
    assert recovered.manifest_ids == recovered_again.manifest_ids
    assert first.pipeline_run.id != new_run.pipeline_run.id
    assert set(first.artifact_ids).isdisjoint(new_run.artifact_ids)
    assert first.semantic_signature == new_run.semantic_signature


def test_failure_lifecycle_stops_at_failed_contradiction(repository) -> None:
    runner = DeterministicRefinery(repository)

    with pytest.raises(RuntimeError, match="injected failure"):
        runner.run("direct_conflict", failure_stage="contradiction")

    stages = repository.list_stage_runs()
    assert [item.stage_name for item in stages] == [
        "evidence_extract",
        "claim_extract",
        "normalize",
        "evidence_link",
        "independence",
        "contradiction",
    ]
    assert [item.status.value for item in stages[:-1]] == ["succeeded"] * 5
    assert stages[-1].status.value == "failed"
    assert stages[-1].error_type == "RuntimeError"
    assert repository.list_pipeline_runs()[0].status.value == "failed"


def test_stage_manifests_match_actual_outputs_and_refs_are_persistent(repository) -> None:
    result = DeterministicRefinery(repository).run("direct_conflict")

    for stage, input_manifest, output_manifest in zip(
        result.stage_runs, result.input_manifests, result.manifests, strict=True
    ):
        assert result.manifest_store.read(stage.input_ref) == input_manifest
        assert result.manifest_store.read(stage.output_ref) == output_manifest
        assert set(output_manifest.output_artifact_ids).issubset(
            set(result.artifact_ids)
            | {item.id for item in result.claim_groups}
            | {item.id for item in result.memberships}
        )
