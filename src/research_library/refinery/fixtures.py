"""Offline semantic fixtures used by the Phase 1B deterministic refinery."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from research_library.domain import EvidenceLinkType, SourceDependencyRelation, SourceType

_FIXTURE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _tuple(value: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(value)


@dataclass(frozen=True, slots=True)
class FixtureSourceSpec:
    key: str
    canonical_uri: str
    title: str
    publisher: str
    source_type: SourceType = SourceType.WEB
    dependency_group: str | None = None
    parent_key: str | None = None
    dependency_relation: SourceDependencyRelation = SourceDependencyRelation.REPOST_OF
    source_quality: float = 0.9
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FixtureSnapshotSpec:
    key: str
    source_key: str
    content: str
    retrieved_at: datetime = _FIXTURE_TIME
    mime_type: str = "text/plain"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FixtureEvidenceSpec:
    key: str
    snapshot_key: str
    text: str
    locator: str = "fixture:1"
    context: str | None = None
    extraction_method: str = "fixture-semantic-backend"


@dataclass(frozen=True, slots=True)
class FixtureClaimSpec:
    key: str
    group_key: str
    group_statement: str
    statement: str
    subject: str
    predicate: str
    object: str
    evidence_keys: tuple[str, ...]
    link_relations: dict[str, EvidenceLinkType] = field(default_factory=dict)
    qualifiers: dict[str, Any] = field(default_factory=dict)
    temporal_scope: str | None = None
    extraction_confidence: float = 0.95

    def relation_for(self, evidence_key: str) -> EvidenceLinkType:
        return EvidenceLinkType(self.link_relations.get(evidence_key, EvidenceLinkType.SUPPORTS))


@dataclass(frozen=True, slots=True)
class FixtureDefinition:
    fixture_id: str
    sources: tuple[FixtureSourceSpec, ...]
    snapshots: tuple[FixtureSnapshotSpec, ...]
    evidences: tuple[FixtureEvidenceSpec, ...]
    claims: tuple[FixtureClaimSpec, ...]
    created_at: datetime = _FIXTURE_TIME
    expected: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))
    metadata: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", _tuple(self.sources))
        object.__setattr__(self, "snapshots", _tuple(self.snapshots))
        object.__setattr__(self, "evidences", _tuple(self.evidences))
        object.__setattr__(self, "claims", _tuple(self.claims))
        object.__setattr__(self, "expected", MappingProxyType(dict(self.expected)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        for values, label in (
            (self.sources, "source"),
            (self.snapshots, "snapshot"),
            (self.evidences, "evidence"),
            (self.claims, "claim"),
        ):
            keys = [item.key for item in values]
            if len(keys) != len(set(keys)):
                raise ValueError(f"duplicate {label} fixture key")
        source_keys = {item.key for item in self.sources}
        snapshot_keys = {item.key for item in self.snapshots}
        evidence_keys = {item.key for item in self.evidences}
        for snapshot in self.snapshots:
            if snapshot.source_key not in source_keys:
                raise ValueError(f"unknown snapshot source: {snapshot.source_key}")
        for evidence in self.evidences:
            if evidence.snapshot_key not in snapshot_keys:
                raise ValueError(f"unknown evidence snapshot: {evidence.snapshot_key}")
        for claim in self.claims:
            if not claim.evidence_keys or not set(claim.evidence_keys) <= evidence_keys:
                raise ValueError(f"claim {claim.key} has invalid evidence keys")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("fixture created_at must be timezone-aware")


def _source(key: str, uri: str, publisher: str, **kwargs: Any) -> FixtureSourceSpec:
    return FixtureSourceSpec(key, uri, key.replace("-", " ").title(), publisher, **kwargs)


def golden_fixtures() -> tuple[FixtureDefinition, ...]:
    """Return the five frozen Phase 1B end-to-end fixtures."""

    independent = FixtureDefinition(
        fixture_id="independent_support",
        sources=(
            _source(
                "source-a", "https://alpha.example/fact", "Alpha Journal", dependency_group="alpha"
            ),
            _source(
                "source-b", "https://beta.example/fact", "Beta Journal", dependency_group="beta"
            ),
        ),
        snapshots=(
            FixtureSnapshotSpec(
                "snapshot-a", "source-a", "The Northstar protocol was released in 2024."
            ),
            FixtureSnapshotSpec(
                "snapshot-b", "source-b", "The Northstar protocol was released in 2024."
            ),
        ),
        evidences=(
            FixtureEvidenceSpec(
                "evidence-a", "snapshot-a", "Northstar protocol release year: 2024."
            ),
            FixtureEvidenceSpec(
                "evidence-b", "snapshot-b", "Northstar protocol release year: 2024."
            ),
        ),
        claims=(
            FixtureClaimSpec(
                "claim-a",
                "northstar-release",
                "Northstar protocol was released in 2024.",
                "Northstar protocol was released in 2024.",
                "northstar",
                "release_year",
                "2024",
                ("evidence-a",),
            ),
            FixtureClaimSpec(
                "claim-b",
                "northstar-release",
                "Northstar protocol was released in 2024.",
                "Northstar protocol released in 2024.",
                "northstar",
                "release_year",
                "2024",
                ("evidence-b",),
            ),
        ),
        expected={"effective_independence_count": 2, "status": "resolved", "atom_status": "active"},
    )

    repost_sources = [
        _source("origin", "https://origin.example/fact", "Origin Wire", dependency_group="origin")
    ]
    repost_snapshots: list[FixtureSnapshotSpec] = []
    repost_evidence: list[FixtureEvidenceSpec] = []
    repost_claims: list[FixtureClaimSpec] = []
    for index in range(10):
        key = f"repost-{index + 1}"
        repost_sources.append(
            _source(
                key,
                f"https://repost-{index + 1}.example/fact",
                f"Repost {index + 1}",
                dependency_group="origin",
                parent_key="origin",
            )
        )
        repost_snapshots.append(
            FixtureSnapshotSpec(f"snapshot-{key}", key, "The Atlas index contains 42 entries.")
        )
        repost_evidence.append(
            FixtureEvidenceSpec(
                f"evidence-{key}", f"snapshot-{key}", "Atlas index entry count: 42."
            )
        )
        repost_claims.append(
            FixtureClaimSpec(
                f"claim-{key}",
                "atlas-count",
                "Atlas index contains 42 entries.",
                "Atlas index contains 42 entries.",
                "atlas",
                "entry_count",
                "42",
                (f"evidence-{key}",),
            )
        )
    repost = FixtureDefinition(
        fixture_id="multi_repost_same_origin",
        sources=tuple(repost_sources),
        snapshots=(
            FixtureSnapshotSpec(
                "snapshot-origin", "origin", "The Atlas index contains 42 entries."
            ),
            *repost_snapshots,
        ),
        evidences=(
            FixtureEvidenceSpec(
                "evidence-origin", "snapshot-origin", "Atlas index entry count: 42."
            ),
            *repost_evidence,
        ),
        claims=(
            FixtureClaimSpec(
                "claim-origin",
                "atlas-count",
                "Atlas index contains 42 entries.",
                "Atlas index contains 42 entries.",
                "atlas",
                "entry_count",
                "42",
                ("evidence-origin",),
            ),
            *repost_claims,
        ),
        expected={"effective_independence_count": 1, "status": "resolved", "atom_status": "active"},
    )

    conflict = FixtureDefinition(
        fixture_id="direct_conflict",
        sources=(
            _source("source-a", "https://a.example/value", "A Lab", dependency_group="a"),
            _source("source-b", "https://b.example/value", "B Lab", dependency_group="b"),
        ),
        snapshots=(
            FixtureSnapshotSpec("snapshot-a", "source-a", "The value is 10."),
            FixtureSnapshotSpec("snapshot-b", "source-b", "The value is 20."),
        ),
        evidences=(
            FixtureEvidenceSpec("evidence-a", "snapshot-a", "Measured value: 10."),
            FixtureEvidenceSpec("evidence-b", "snapshot-b", "Measured value: 20."),
        ),
        claims=(
            FixtureClaimSpec(
                "claim-a",
                "measured-value",
                "The measured value is stable.",
                "The measured value is 10.",
                "sample",
                "value",
                "10",
                ("evidence-a",),
            ),
            FixtureClaimSpec(
                "claim-b",
                "measured-value",
                "The measured value is stable.",
                "The measured value is 20.",
                "sample",
                "value",
                "20",
                ("evidence-b",),
            ),
        ),
        expected={"status": "conflicting", "atom_status": "withheld"},
    )

    qualified = FixtureDefinition(
        fixture_id="qualified_support",
        sources=(
            _source(
                "source",
                "https://qualifier.example/rule",
                "Qualifier Review",
                dependency_group="qualifier",
            ),
        ),
        snapshots=(
            FixtureSnapshotSpec("snapshot", "source", "The rule applies only to archived records."),
        ),
        evidences=(
            FixtureEvidenceSpec(
                "evidence", "snapshot", "The rule applies only to archived records."
            ),
        ),
        claims=(
            FixtureClaimSpec(
                "claim",
                "archived-rule",
                "The rule applies to archived records.",
                "The rule applies to archived records.",
                "rule",
                "applies_to",
                "archived_records",
                ("evidence",),
                {"evidence": EvidenceLinkType.QUALIFIES},
                qualifiers={"condition": "archived_records"},
            ),
        ),
        expected={"status": "resolved", "atom_status": "active", "validity": "conditional"},
    )

    history = FixtureDefinition(
        fixture_id="snapshot_history",
        sources=(
            _source(
                "source",
                "https://history.example/fact",
                "History Ledger",
                dependency_group="history",
            ),
        ),
        snapshots=(
            FixtureSnapshotSpec(
                "snapshot-old",
                "source",
                "The archive listed 7 entries in 2023.",
                retrieved_at=datetime(2023, 1, 1, tzinfo=UTC),
            ),
            FixtureSnapshotSpec(
                "snapshot-new",
                "source",
                "The archive listed 9 entries in 2025.",
                retrieved_at=datetime(2025, 1, 1, tzinfo=UTC),
            ),
        ),
        evidences=(
            FixtureEvidenceSpec("evidence-old", "snapshot-old", "Archive entry count in 2023: 7."),
            FixtureEvidenceSpec("evidence-new", "snapshot-new", "Archive entry count in 2025: 9."),
        ),
        claims=(
            FixtureClaimSpec(
                "claim-old",
                "archive-2023",
                "The archive listed 7 entries in 2023.",
                "The archive listed 7 entries in 2023.",
                "archive",
                "entry_count",
                "7",
                ("evidence-old",),
                temporal_scope="2023",
            ),
            FixtureClaimSpec(
                "claim-new",
                "archive-2025",
                "The archive listed 9 entries in 2025.",
                "The archive listed 9 entries in 2025.",
                "archive",
                "entry_count",
                "9",
                ("evidence-new",),
                temporal_scope="2025",
            ),
        ),
        expected={"snapshot_count": 2, "atom_count": 2, "history_preserved": True},
    )
    return (independent, repost, conflict, qualified, history)


GOLDEN_FIXTURE_IDS = tuple(item.fixture_id for item in golden_fixtures())


def get_golden_fixture(fixture_id: str) -> FixtureDefinition:
    for fixture in golden_fixtures():
        if fixture.fixture_id == fixture_id:
            return fixture
    raise KeyError(f"unknown Phase 1B golden fixture: {fixture_id}")
