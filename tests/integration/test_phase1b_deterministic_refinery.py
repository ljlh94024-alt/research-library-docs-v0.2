from research_library.domain import EvidenceLinkType, KnowledgeAtomStatus, ResolvedClaimStatus
from research_library.refinery import (
    CANONICAL_STAGE_NAMES,
    DETERMINISTIC_PIPELINE_VERSION,
    GOLDEN_FIXTURE_IDS,
    DeterministicRefinery,
    FixtureSemanticBackend,
    StageManifest,
    stable_artifact_id,
)


def test_phase1b_runs_all_five_golden_fixtures(repository) -> None:
    runner = DeterministicRefinery(repository, FixtureSemanticBackend())

    results = {fixture_id: runner.run(fixture_id) for fixture_id in GOLDEN_FIXTURE_IDS}

    assert set(results) == set(GOLDEN_FIXTURE_IDS)
    for fixture_id, result in results.items():
        assert result.pipeline_run.pipeline_version == DETERMINISTIC_PIPELINE_VERSION
        assert [item.stage_name for item in result.stage_runs] == list(CANONICAL_STAGE_NAMES)
        assert all(item.status.value == "succeeded" for item in result.stage_runs)
        assert len(result.manifests) == 9
        assert all(
            item.output_ref == manifest.ref
            for item, manifest in zip(result.stage_runs, result.manifests, strict=True)
        )
        assert all(
            repository.get_processing_provenance(atom.id).is_complete for atom in result.atoms
        )
        assert result.metrics["fixture_expected"]

    assert results["independent_support"].metrics["effective_independence_count"] == 2
    assert results["independent_support"].active_atoms[0].status is KnowledgeAtomStatus.ACTIVE
    assert results["independent_support"].assessments[0].score > 0.8

    repost = results["multi_repost_same_origin"]
    assert len(repost.sources) == 11
    assert len(repost.dependencies) == 10
    assert repost.metrics["effective_independence_count"] == 1

    conflict = results["direct_conflict"]
    assert len(conflict.contradictions) == 1
    assert conflict.decisions[0].status is ResolvedClaimStatus.CONFLICTING
    assert conflict.atoms[0].status is KnowledgeAtomStatus.WITHHELD
    assert conflict.assessments[0].publish_cap == 0.2
    assert conflict.assessments[0].score <= 0.2

    qualified = results["qualified_support"]
    assert {link.relation_type for link in qualified.evidence_links} == {EvidenceLinkType.QUALIFIES}
    assert qualified.atoms[0].validity == "conditional"

    history = results["snapshot_history"]
    assert len(history.snapshots) == 2
    assert len(history.atoms) == 2
    assert (
        repository.read_snapshot(history.snapshots[0].id)
        == b"The archive listed 7 entries in 2023."
    )
    assert (
        repository.read_snapshot(history.snapshots[1].id)
        == b"The archive listed 9 entries in 2025."
    )


def test_phase1b_replay_keeps_ids_and_manifests(repository) -> None:
    runner = DeterministicRefinery(repository)

    first = runner.run("snapshot_history")
    second = runner.run("snapshot_history")

    assert first.pipeline_run.id == second.pipeline_run.id
    assert first.artifact_ids == second.artifact_ids
    assert first.manifest_ids == second.manifest_ids
    assert len(repository.list_stage_runs(first.pipeline_run.id)) == 9


def test_phase1b_ids_and_manifests_are_content_addressed() -> None:
    assert stable_artifact_id("claim", "fixture", "same") == stable_artifact_id(
        "claim", "fixture", "same"
    )
    assert stable_artifact_id("claim", "fixture", "same") != stable_artifact_id(
        "claim", "fixture", "changed"
    )

    first = StageManifest("normalize", DETERMINISTIC_PIPELINE_VERSION, ("a",), ("b",))
    second = StageManifest("normalize", DETERMINISTIC_PIPELINE_VERSION, ("a",), ("c",))
    assert first.manifest_id == first.manifest_id
    assert first.content_hash != second.content_hash
    assert first.ref.startswith("manifest:manifest-")
