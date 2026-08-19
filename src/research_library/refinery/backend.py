"""Offline FixtureSemanticBackend implementing the provider-neutral seam."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC
from typing import Any

from research_library.domain import Source, SourceSnapshot

from .fixtures import (
    GOLDEN_FIXTURE_IDS,
    FixtureClaimSpec,
    FixtureDefinition,
    FixtureEvidenceSpec,
    FixtureSnapshotSpec,
    FixtureSourceSpec,
    golden_fixtures,
)
from .manifests import stable_artifact_id
from .semantic import (
    ClaimCandidate,
    DependencySignal,
    EvidenceCandidate,
    EvidenceRelationCandidate,
    SemanticBackend,
    SemanticBatch,
)


class FixtureSemanticBackend:
    """Return immutable semantic candidates from local fixture annotations only."""

    def __init__(self, fixtures: tuple[FixtureDefinition, ...] | None = None) -> None:
        self._fixtures = {item.fixture_id: item for item in (fixtures or golden_fixtures())}

    @property
    def fixture_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._fixtures))

    def list_fixture_ids(self) -> tuple[str, ...]:
        return self.fixture_ids

    def get_fixture(self, fixture_id: str) -> FixtureDefinition:
        try:
            return self._fixtures[fixture_id]
        except KeyError as exc:
            raise KeyError(f"unknown fixture: {fixture_id}") from exc

    fixture = get_fixture

    @staticmethod
    def source_id(fixture_id: str, source_key: str, canonical_uri: str) -> str:
        return stable_artifact_id("source", fixture_id, source_key, canonical_uri)

    @staticmethod
    def snapshot_id(fixture_id: str, snapshot: FixtureSnapshotSpec) -> str:
        return stable_artifact_id("snapshot", fixture_id, snapshot.key, snapshot.content)

    def iter_sources(self, fixture_id: str) -> Iterator[FixtureSourceSpec]:
        return iter(self.get_fixture(fixture_id).sources)

    def iter_snapshots(self, fixture_id: str) -> Iterator[FixtureSnapshotSpec]:
        return iter(self.get_fixture(fixture_id).snapshots)

    def iter_evidence(self, fixture_id: str) -> Iterator[FixtureEvidenceSpec]:
        return iter(self.get_fixture(fixture_id).evidences)

    def iter_claims(self, fixture_id: str) -> Iterator[FixtureClaimSpec]:
        return iter(self.get_fixture(fixture_id).claims)

    def seed_inputs(
        self,
        repository: Any,
        fixture_id: str,
        snapshot_keys: tuple[str, ...] | None = None,
    ) -> tuple[SourceSnapshot, ...]:
        """Seed Source/SourceSnapshot before PipelineRun starts.

        This is ingestion-harness behavior, not an evidence_extract stage.
        """

        fixture = self.get_fixture(fixture_id)
        source_ids: dict[str, str] = {}
        for spec in fixture.sources:
            source_id = self.source_id(fixture_id, spec.key, spec.canonical_uri)
            source_ids[spec.key] = source_id
            repository.save_source(
                Source(
                    id=source_id,
                    source_type=spec.source_type,
                    canonical_uri=spec.canonical_uri,
                    title=spec.title,
                    publisher=spec.publisher,
                    metadata={
                        **spec.metadata,
                        "fixture_source_key": spec.key,
                        "source_quality": spec.source_quality,
                    },
                    created_at=fixture.created_at,
                )
            )
        selected = set(snapshot_keys or (item.key for item in fixture.snapshots))
        snapshots: list[SourceSnapshot] = []
        for spec in fixture.snapshots:
            if spec.key not in selected:
                continue
            snapshot = repository.create_snapshot(
                source_ids[spec.source_key],
                spec.content,
                snapshot_id=self.snapshot_id(fixture_id, spec),
                retrieved_at=spec.retrieved_at,
                mime_type=spec.mime_type,
                metadata={"fixture_snapshot_key": spec.key, **spec.metadata},
                created_by_stage_run_id=None,
            )
            snapshots.append(snapshot)
        if not snapshots:
            raise ValueError(f"fixture {fixture_id} produced no selected snapshots")
        return tuple(snapshots)

    def collect(self, fixture_id: str, snapshot_ids: tuple[str, ...]) -> SemanticBatch:
        fixture = self.get_fixture(fixture_id)
        snapshots_by_id = {self.snapshot_id(fixture_id, item): item for item in fixture.snapshots}
        snapshots_by_key = {item.key: item for item in fixture.snapshots}
        selected_keys = {
            snapshots_by_id[snapshot_id].key
            for snapshot_id in snapshot_ids
            if snapshot_id in snapshots_by_id
        }
        evidence_by_key = {
            item.key: item for item in fixture.evidences if item.snapshot_key in selected_keys
        }
        evidence = tuple(
            EvidenceCandidate(
                candidate_id=item.key,
                snapshot_id=self.snapshot_id(fixture_id, snapshots_by_key[next_key]),
                text=item.text,
                locator=item.locator,
                context=item.context,
                extraction_method=item.extraction_method,
            )
            for next_key in selected_keys
            for item in fixture.evidences
            if item.snapshot_key == next_key
        )
        claim_specs = tuple(
            item for item in fixture.claims if set(item.evidence_keys) & set(evidence_by_key)
        )
        claims = tuple(
            ClaimCandidate(
                candidate_id=item.key,
                statement=item.statement,
                subject=item.subject,
                predicate=item.predicate,
                object=item.object,
                qualifiers=dict(item.qualifiers),
                temporal_scope=item.temporal_scope,
                extraction_confidence=item.extraction_confidence,
                evidence_candidate_ids=tuple(
                    key for key in item.evidence_keys if key in evidence_by_key
                ),
            )
            for item in claim_specs
        )
        relations = tuple(
            EvidenceRelationCandidate(
                evidence_candidate_id=evidence_key,
                claim_candidate_id=item.key,
                relation_type=item.relation_for(evidence_key),
                rationale=f"fixture semantic relation: {item.relation_for(evidence_key).value}",
            )
            for item in claim_specs
            for evidence_key in item.evidence_keys
            if evidence_key in evidence_by_key
        )
        source_by_key = {item.key: item for item in fixture.sources}
        source_ids = {
            key: self.source_id(fixture_id, key, spec.canonical_uri)
            for key, spec in source_by_key.items()
        }
        dependencies = tuple(
            DependencySignal(
                source_id=source_ids[item.key],
                parent_source_id=source_ids[item.parent_key],
                relation_type=item.dependency_relation,
                dependency_group=item.dependency_group,
                independence_score=0.0,
                reason="fixture semantic dependency signal",
                signals={"canonical_uri": item.canonical_uri},
            )
            for item in fixture.sources
            if item.parent_key is not None
            and item.key
            in {
                source_by_key[snap.source_key].key
                for snap in fixture.snapshots
                if snap.key in selected_keys
            }
        )
        return SemanticBatch(
            evidence=evidence,
            claims=claims,
            relations=relations,
            dependencies=dependencies,
            reference_time=fixture.created_at.astimezone(UTC),
        )


__all__ = [
    "FixtureSemanticBackend",
    "FixtureClaimSpec",
    "FixtureDefinition",
    "FixtureEvidenceSpec",
    "FixtureSnapshotSpec",
    "FixtureSourceSpec",
    "GOLDEN_FIXTURE_IDS",
    "SemanticBackend",
]
