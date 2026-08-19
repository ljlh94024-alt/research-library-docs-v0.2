"""Deterministic, offline semantic backend for frozen Phase 1B fixtures."""

from __future__ import annotations

from collections.abc import Iterator

from .fixtures import (
    GOLDEN_FIXTURE_IDS,
    FixtureClaimSpec,
    FixtureDefinition,
    FixtureEvidenceSpec,
    FixtureSnapshotSpec,
    FixtureSourceSpec,
    get_golden_fixture,
    golden_fixtures,
)


class FixtureSemanticBackend:
    """Provide semantic records from local fixtures only.

    The backend intentionally has no provider, network, API, model, or vector
    store boundary.  It is the Phase 1B seam that later phases may replace.
    """

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

    def iter_sources(self, fixture_id: str) -> Iterator[FixtureSourceSpec]:
        return iter(self.get_fixture(fixture_id).sources)

    def iter_snapshots(self, fixture_id: str) -> Iterator[FixtureSnapshotSpec]:
        return iter(self.get_fixture(fixture_id).snapshots)

    def iter_evidence(self, fixture_id: str) -> Iterator[FixtureEvidenceSpec]:
        return iter(self.get_fixture(fixture_id).evidences)

    def iter_claims(self, fixture_id: str) -> Iterator[FixtureClaimSpec]:
        return iter(self.get_fixture(fixture_id).claims)


__all__ = [
    "FixtureSemanticBackend",
    "FixtureClaimSpec",
    "FixtureDefinition",
    "FixtureEvidenceSpec",
    "FixtureSnapshotSpec",
    "FixtureSourceSpec",
    "GOLDEN_FIXTURE_IDS",
    "get_golden_fixture",
]
