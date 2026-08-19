"""Phase 1B deterministic nine-stage knowledge refinery."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from research_library.domain import (
    Claim,
    ClaimGroup,
    ClaimGroupMembership,
    ConfidenceAssessment,
    Contradiction,
    ContradictionSeverity,
    ContradictionStatus,
    ContradictionType,
    Evidence,
    EvidenceLink,
    EvidenceLinkType,
    KnowledgeAtom,
    KnowledgeAtomStatus,
    PipelineRun,
    PipelineRunStatus,
    ResolutionClaimInput,
    ResolutionDecision,
    ResolutionEvidenceInput,
    ResolutionInputRole,
    ResolvedClaim,
    ResolvedClaimStatus,
    Source,
    SourceDependency,
    SourceSnapshot,
    StageRun,
    StageRunStatus,
)
from research_library.storage.repository import Repository

from .manifests import StageManifest, StageManifestStore, stable_artifact_id
from .semantic import SemanticBackend

DETERMINISTIC_PIPELINE_VERSION = "phase1b-deterministic-v2"
CANONICAL_STAGE_NAMES = (
    "evidence_extract",
    "claim_extract",
    "normalize",
    "evidence_link",
    "independence",
    "contradiction",
    "resolve",
    "confidence",
    "atom_build",
)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, round(value, 6)))


def _normalized_text(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip().casefold()


class NormalizationPolicy:
    version = "normalization-v2-nfkc-casefold"

    @staticmethod
    def comparison_key(claim: Claim) -> str:
        """Build a value-independent key from the persisted Claim only."""

        qualifiers = {
            _normalized_text(str(key)): _normalized_text(str(value))
            for key, value in claim.qualifiers.items()
        }
        return json.dumps(
            {
                "subject": _normalized_text(claim.subject),
                "predicate": _normalized_text(claim.predicate),
                "qualifiers": qualifiers,
                "temporal_scope": _normalized_text(claim.temporal_scope),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def signature(claim: Claim) -> str:
        return stable_artifact_id("normalized-claim", NormalizationPolicy.comparison_key(claim))

    @staticmethod
    def canonical_statement(claim: Claim) -> str:
        parts = [item for item in (claim.subject, claim.predicate) if item]
        if claim.temporal_scope:
            parts.append(claim.temporal_scope)
        return " ".join(_normalized_text(item) for item in parts) or _normalized_text(
            claim.statement
        )


class IndependencePolicy:
    version = "independence-v2-persisted-dependencies"

    @staticmethod
    def effective_unit(source_id: str, dependencies: tuple[SourceDependency, ...]) -> str:
        by_source = {item.source_id: item for item in dependencies}
        by_parent_group = {
            item.parent_source_id: item.dependency_group
            for item in dependencies
            if item.dependency_group
        }
        if source_id in by_parent_group:
            return f"dependency-group:{by_parent_group[source_id]}"
        current = source_id
        seen: set[str] = set()
        while current not in seen:
            seen.add(current)
            dependency = by_source.get(current)
            if dependency is None:
                return current
            if dependency.dependency_group:
                return f"dependency-group:{dependency.dependency_group}"
            current = dependency.parent_source_id
        return current

    @classmethod
    def count(cls, source_ids: set[str], dependencies: tuple[SourceDependency, ...]) -> int:
        return len({cls.effective_unit(source_id, dependencies) for source_id in source_ids})


class ContradictionPolicy:
    version = "contradiction-v2-temporal-aware"

    @staticmethod
    def classify(left: Claim, right: Claim) -> ContradictionType | None:
        if (
            left.subject is None
            or right.subject is None
            or _normalized_text(left.subject) != _normalized_text(right.subject)
            or left.predicate is None
            or right.predicate is None
            or _normalized_text(left.predicate) != _normalized_text(right.predicate)
            or left.object is None
            or right.object is None
            or _normalized_text(left.object) == _normalized_text(right.object)
        ):
            return None
        if left.temporal_scope != right.temporal_scope:
            return ContradictionType.TEMPORAL
        return ContradictionType.DIRECT

    @classmethod
    def incompatible(cls, left: Claim, right: Claim) -> bool:
        return cls.classify(left, right) is ContradictionType.DIRECT


@dataclass(frozen=True, slots=True)
class ResolutionOutcome:
    status: ResolvedClaimStatus
    validity: str | None
    reason: str
    selected_value: str | None
    supporting_units: frozenset[str]
    supported_values: tuple[str, ...]


class ResolutionPolicy:
    version = "resolution-v2-independent-value-ranking"

    @classmethod
    def evaluate(
        cls,
        claims: tuple[Claim, ...],
        links: tuple[EvidenceLink, ...],
        contradictions: tuple[Contradiction, ...],
        source_for_evidence: Callable[[str], str],
        dependencies: tuple[SourceDependency, ...],
    ) -> ResolutionOutcome:
        claim_by_id = {item.id: item for item in claims}
        support_units_by_value: dict[str, set[str]] = {}
        support_links = [item for item in links if item.relation_type is EvidenceLinkType.SUPPORTS]
        for link in support_links:
            claim = claim_by_id[link.claim_id]
            value = _normalized_text(claim.object)
            support_units_by_value.setdefault(value, set()).add(
                IndependencePolicy.effective_unit(
                    source_for_evidence(link.evidence_id), dependencies
                )
            )
        supported_values = tuple(sorted(key for key in support_units_by_value if key))
        direct_conflict = any(item.type is ContradictionType.DIRECT for item in contradictions)
        temporal_conflict = any(item.type is ContradictionType.TEMPORAL for item in contradictions)
        if direct_conflict or len(supported_values) > 1:
            return ResolutionOutcome(
                ResolvedClaimStatus.CONFLICTING,
                None,
                "independent supporting units disagree on candidate values",
                None,
                frozenset().union(*(support_units_by_value[value] for value in supported_values)),
                supported_values,
            )
        if temporal_conflict:
            return ResolutionOutcome(
                ResolvedClaimStatus.HISTORICAL_CHANGE,
                "historical",
                "evidence differs by temporal scope",
                None,
                frozenset().union(*(support_units_by_value[value] for value in supported_values)),
                supported_values,
            )
        if not supported_values:
            return ResolutionOutcome(
                ResolvedClaimStatus.INSUFFICIENT_EVIDENCE,
                None,
                "no independent SUPPORTS evidence selected a candidate value",
                None,
                frozenset(),
                (),
            )
        selected_value = supported_values[0]
        return ResolutionOutcome(
            ResolvedClaimStatus.RESOLVED,
            None,
            "one candidate value is supported; publication still requires the evidence floor",
            selected_value,
            frozenset(support_units_by_value[selected_value]),
            supported_values,
        )


class ConfidencePolicy:
    version = "deterministic-confidence-v1"
    WEIGHTS = {
        "source_quality": 0.15,
        "evidence_directness": 0.20,
        "source_independence": 0.25,
        "agreement": 0.20,
        "freshness": 0.10,
        "extraction_confidence": 0.10,
    }
    DIRECTNESS = {
        EvidenceLinkType.SUPPORTS: 1.0,
        EvidenceLinkType.QUALIFIES: 0.75,
        EvidenceLinkType.MENTIONS: 0.25,
        EvidenceLinkType.CONTRADICTS: 1.0,
    }
    CONTRADICTION_PENALTY = {
        ContradictionSeverity.LOW: 0.3,
        ContradictionSeverity.MEDIUM: 0.6,
        ContradictionSeverity.HIGH: 1.0,
    }
    STATUS_CAP = {
        ResolvedClaimStatus.CONFLICTING: 0.30,
        ResolvedClaimStatus.INSUFFICIENT_EVIDENCE: 0.40,
        ResolvedClaimStatus.UNRESOLVED: 0.50,
        ResolvedClaimStatus.HISTORICAL_CHANGE: 0.70,
    }

    @staticmethod
    def freshness(reference_time: datetime, retrieved_at: datetime) -> float:
        age_days = max(0.0, (reference_time - retrieved_at).total_seconds() / 86400)
        if age_days <= 30:
            return 1.0
        if age_days <= 180:
            return 0.8
        if age_days <= 365:
            return 0.6
        return 0.4

    @classmethod
    def assess(
        cls,
        *,
        status: ResolvedClaimStatus,
        claims: tuple[Claim, ...],
        links: tuple[EvidenceLink, ...],
        source_quality: float,
        independent_support_units: int,
        agreement: float,
        freshness: float,
        contradictions: tuple[Contradiction, ...],
    ) -> dict[str, Any]:
        directness = sum(cls.DIRECTNESS[item.relation_type] for item in links) / max(len(links), 1)
        extraction = sum(item.extraction_confidence or 0.0 for item in claims) / max(len(claims), 1)
        floor = independent_support_units >= 2
        penalty = max(
            (cls.CONTRADICTION_PENALTY[item.severity] for item in contradictions),
            default=0.0,
        )
        components = {
            "source_quality": _clamp(source_quality),
            "evidence_directness": _clamp(directness),
            "source_independence": _clamp(independent_support_units / 2),
            "agreement": _clamp(agreement),
            "freshness": _clamp(freshness),
            "extraction_confidence": _clamp(extraction),
        }
        base = sum(components[name] * weight for name, weight in cls.WEIGHTS.items())
        penalized = base * (1 - 0.5 * penalty)
        status_cap = cls.STATUS_CAP.get(status)
        publish_cap = status_cap
        if not floor:
            publish_cap = min(publish_cap, 0.65) if publish_cap is not None else 0.65
        score = _clamp(min(penalized, publish_cap or 1.0))
        return {
            **components,
            "contradiction_penalty": penalty,
            "publish_cap": publish_cap,
            "evidence_floor_met": floor,
            "score": score,
            "reasons": {
                "policy": [cls.version, f"weights={cls.WEIGHTS}"],
                "evidence": [
                    f"independent_support_units={independent_support_units}",
                    f"floor_met={floor}",
                ],
                "agreement": [f"agreement={components['agreement']}"],
                "freshness": [f"freshness={components['freshness']}"],
                "contradiction": [f"penalty={penalty}"],
            },
        }


class AtomPolicy:
    version = "atom-v2-publication-threshold"

    @staticmethod
    def status(
        status: ResolvedClaimStatus, evidence_floor_met: bool, confidence: float
    ) -> KnowledgeAtomStatus:
        return (
            KnowledgeAtomStatus.ACTIVE
            if status is ResolvedClaimStatus.RESOLVED and evidence_floor_met and confidence >= 0.75
            else KnowledgeAtomStatus.WITHHELD
        )


@dataclass(frozen=True, slots=True)
class DeterministicRefineryResult:
    fixture_id: str
    pipeline_run: PipelineRun
    stage_runs: tuple[StageRun, ...]
    manifests: tuple[StageManifest, ...]
    input_manifests: tuple[StageManifest, ...]
    manifest_store: StageManifestStore
    snapshots: tuple[SourceSnapshot, ...] = ()
    sources: tuple[Source, ...] = ()
    evidences: tuple[Evidence, ...] = ()
    claims: tuple[Claim, ...] = ()
    claim_groups: tuple[ClaimGroup, ...] = ()
    memberships: tuple[ClaimGroupMembership, ...] = ()
    evidence_links: tuple[EvidenceLink, ...] = ()
    dependencies: tuple[SourceDependency, ...] = ()
    contradictions: tuple[Contradiction, ...] = ()
    decisions: tuple[ResolutionDecision, ...] = ()
    claim_inputs: tuple[ResolutionClaimInput, ...] = ()
    evidence_inputs: tuple[ResolutionEvidenceInput, ...] = ()
    assessments: tuple[ConfidenceAssessment, ...] = ()
    resolved_claims: tuple[ResolvedClaim, ...] = ()
    atoms: tuple[KnowledgeAtom, ...] = ()
    semantic_signature: tuple[tuple[str, ...], ...] = ()
    metrics: dict[str, Any] | None = None

    @property
    def knowledge_atoms(self) -> tuple[KnowledgeAtom, ...]:
        return self.atoms

    @property
    def active_atoms(self) -> tuple[KnowledgeAtom, ...]:
        return tuple(item for item in self.atoms if item.status is KnowledgeAtomStatus.ACTIVE)

    @property
    def withheld_atoms(self) -> tuple[KnowledgeAtom, ...]:
        return tuple(item for item in self.atoms if item.status is KnowledgeAtomStatus.WITHHELD)

    @property
    def artifact_ids(self) -> tuple[str, ...]:
        collections = (
            self.evidences,
            self.claims,
            self.claim_groups,
            self.evidence_links,
            self.dependencies,
            self.contradictions,
            self.decisions,
            self.claim_inputs,
            self.evidence_inputs,
            self.assessments,
            self.resolved_claims,
            self.atoms,
        )
        return tuple(item.id for values in collections for item in values)

    @property
    def manifest_ids(self) -> tuple[str, ...]:
        return tuple(item.manifest_id for item in self.manifests)


class DeterministicRefinery:
    """Execute nine stages over a replaceable SemanticBackend."""

    def __init__(
        self,
        repository: Repository,
        backend: SemanticBackend | None = None,
        *,
        pipeline_version: str = DETERMINISTIC_PIPELINE_VERSION,
        manifest_store: StageManifestStore | None = None,
        manifest_root: str | Path | None = None,
    ) -> None:
        if not pipeline_version.startswith("phase1b"):
            raise ValueError("Phase 1B pipeline version must start with phase1b")
        self.repository = repository
        if backend is None:
            from .backend import FixtureSemanticBackend

            backend = FixtureSemanticBackend()
        self.backend = backend
        if manifest_store is not None:
            self.manifest_store = manifest_store
        else:
            root = manifest_root
            if root is None:
                snapshot_store = getattr(repository, "snapshot_store", None)
                root = Path(snapshot_store.root).parent / "refinery-manifests"
            self.manifest_store = StageManifestStore(root)
        self.pipeline_version = pipeline_version

    def run(
        self,
        fixture_id: str,
        *,
        snapshot_keys: tuple[str, ...] | None = None,
        recovery_key: str | None = None,
        run_key: str | None = None,
        failure_stage: str | None = None,
    ) -> DeterministicRefineryResult:
        if recovery_key is not None and run_key is not None:
            raise ValueError("use recovery_key or run_key, not both")
        recovery_key = recovery_key or run_key
        snapshots = self.backend.seed_inputs(self.repository, fixture_id, snapshot_keys)
        snapshot_ids = tuple(item.id for item in snapshots)
        batch = self.backend.collect(fixture_id, snapshot_ids)
        now = (batch.reference_time or datetime.now(UTC)).astimezone(UTC)
        pipeline_id = (
            stable_artifact_id("pipeline-run", fixture_id, self.pipeline_version, recovery_key)
            if recovery_key is not None
            else f"pipeline-run-{uuid4().hex}"
        )
        pipeline = PipelineRun(
            id=pipeline_id,
            pipeline_version=self.pipeline_version,
            status=PipelineRunStatus.STARTED,
            started_at=now,
            input_ref=f"snapshots:{stable_artifact_id('snapshot-input', *snapshot_ids)}",
            metadata={"fixture_id": fixture_id, "backend": type(self.backend).__name__},
        )
        existing_pipeline = self.repository.get_pipeline_run(pipeline_id)
        pipeline_replay = existing_pipeline is not None
        if existing_pipeline is not None:
            if existing_pipeline.status is PipelineRunStatus.FAILED:
                raise RuntimeError(f"recovery key belongs to failed pipeline: {pipeline_id}")
            pipeline = existing_pipeline
        else:
            self.repository.save_pipeline_run(pipeline)

        stage_runs: list[StageRun] = []
        output_manifests: list[StageManifest] = []
        input_manifests: list[StageManifest] = []
        prior_ids = snapshot_ids
        evidence_by_candidate: dict[str, Evidence] = {}
        claim_by_candidate: dict[str, Claim] = {}
        group_by_signature: dict[str, ClaimGroup] = {}
        group_signature_by_id: dict[str, str] = {}
        memberships: list[ClaimGroupMembership] = []
        links: list[EvidenceLink] = []
        dependencies: list[SourceDependency] = []
        contradictions: list[Contradiction] = []
        decisions: list[ResolutionDecision] = []
        claim_inputs: list[ResolutionClaimInput] = []
        evidence_inputs: list[ResolutionEvidenceInput] = []
        assessments: list[ConfidenceAssessment] = []
        resolved_claims: list[ResolvedClaim] = []
        atoms: list[KnowledgeAtom] = []
        outcomes: dict[str, ResolutionOutcome] = {}

        def source_for_evidence(evidence_id: str) -> str:
            evidence = self.repository.get_evidence(evidence_id)
            if evidence is None:
                raise RuntimeError(f"missing evidence: {evidence_id}")
            snapshot = self.repository.get_snapshot(evidence.snapshot_id)
            if snapshot is None:
                raise RuntimeError(f"missing snapshot: {evidence.snapshot_id}")
            return snapshot.source_id

        def execute_stage(
            stage_name: str,
            action: Callable[[str], tuple[str, ...]],
            *,
            metadata: dict[str, str] | None = None,
        ) -> None:
            nonlocal pipeline, prior_ids
            stage_id = stable_artifact_id("stage-run", pipeline_id, stage_name)
            common_metadata = {
                "pipeline_run_id": pipeline_id,
                "fixture_id": fixture_id,
                "kind": "input",
                **(metadata or {}),
            }
            input_manifest = StageManifest(
                stage_name, self.pipeline_version, prior_ids, (), common_metadata
            )
            self.manifest_store.write(input_manifest)
            input_manifests.append(input_manifest)
            started = StageRun(
                id=stage_id,
                pipeline_run_id=pipeline_id,
                stage_name=stage_name,
                stage_version=self.pipeline_version,
                status=StageRunStatus.STARTED,
                model="deterministic-semantic-backend",
                provider="offline",
                input_ref=input_manifest.ref,
                started_at=now,
            )
            existing_stage = self.repository.get_stage_run(stage_id)
            if existing_stage is None:
                self.repository.save_stage_run(started)
            elif existing_stage.status is StageRunStatus.FAILED:
                raise RuntimeError(f"recovery stage is failed: {stage_id}")
            elif existing_stage.status is StageRunStatus.SUCCEEDED:
                started = existing_stage
            try:
                if failure_stage == stage_name:
                    raise RuntimeError(f"injected failure at {stage_name}")
                actual_output_ids = tuple(action(stage_id))
                output_manifest = StageManifest(
                    stage_name,
                    self.pipeline_version,
                    prior_ids,
                    actual_output_ids,
                    {
                        "pipeline_run_id": pipeline_id,
                        "fixture_id": fixture_id,
                        "kind": "output",
                        **(metadata or {}),
                    },
                )
                self.manifest_store.write(output_manifest)
                succeeded = replace(
                    started,
                    status=StageRunStatus.SUCCEEDED,
                    finished_at=now,
                    output_ref=output_manifest.ref,
                )
                if existing_stage is None or existing_stage.status is StageRunStatus.STARTED:
                    self.repository.save_stage_run(succeeded)
                else:
                    succeeded = existing_stage
                stage_runs.append(succeeded)
                output_manifests.append(output_manifest)
                prior_ids = actual_output_ids
            except Exception as exc:
                failed = replace(
                    started,
                    status=StageRunStatus.FAILED,
                    finished_at=now,
                    error_type=type(exc).__name__,
                    error=str(exc) or type(exc).__name__,
                )
                if existing_stage is None or existing_stage.status is StageRunStatus.STARTED:
                    self.repository.save_stage_run(failed)
                stage_runs.append(failed)
                pipeline = replace(
                    pipeline,
                    status=PipelineRunStatus.FAILED,
                    finished_at=now,
                    error=f"{stage_name}: {type(exc).__name__}: {exc}",
                )
                self.repository.save_pipeline_run(pipeline)
                raise

        def evidence_extract(stage_id: str) -> tuple[str, ...]:
            for candidate in batch.evidence:
                evidence = Evidence(
                    id=stable_artifact_id("evidence", stage_id, candidate.candidate_id),
                    snapshot_id=candidate.snapshot_id,
                    text=candidate.text,
                    locator=candidate.locator,
                    context=candidate.context,
                    extraction_method=candidate.extraction_method,
                    created_at=now,
                    created_by_stage_run_id=stage_id,
                )
                self.repository.save_evidence(evidence)
                evidence_by_candidate[candidate.candidate_id] = evidence
            return tuple(item.id for item in evidence_by_candidate.values())

        def claim_extract(stage_id: str) -> tuple[str, ...]:
            for candidate in batch.claims:
                claim = Claim(
                    id=stable_artifact_id("claim", stage_id, candidate.candidate_id),
                    statement=candidate.statement,
                    subject=candidate.subject,
                    predicate=candidate.predicate,
                    object=candidate.object,
                    qualifiers=dict(candidate.qualifiers),
                    temporal_scope=candidate.temporal_scope,
                    extraction_confidence=candidate.extraction_confidence,
                    created_at=now,
                    created_by_stage_run_id=stage_id,
                )
                self.repository.save_claim(claim)
                claim_by_candidate[candidate.candidate_id] = claim
            return tuple(item.id for item in claim_by_candidate.values())

        def normalize(stage_id: str) -> tuple[str, ...]:
            by_signature: dict[str, list[Claim]] = {}
            for claim in claim_by_candidate.values():
                by_signature.setdefault(NormalizationPolicy.signature(claim), []).append(claim)
            for signature in sorted(by_signature):
                claims = sorted(by_signature[signature], key=lambda item: item.id)
                first = claims[0]
                group = ClaimGroup(
                    id=stable_artifact_id("claim-group", stage_id, signature),
                    canonical_key=f"{stage_id}:{signature}",
                    canonical_statement=NormalizationPolicy.canonical_statement(first),
                    subject=first.subject,
                    predicate=first.predicate,
                    qualifiers=first.qualifiers,
                    temporal_scope=first.temporal_scope,
                    created_at=now,
                    created_by_stage_run_id=stage_id,
                )
                self.repository.save_claim_group(group)
                group_by_signature[signature] = group
                group_signature_by_id[group.id] = signature
                for claim in claims:
                    membership = ClaimGroupMembership(
                        claim_group_id=group.id,
                        claim_id=claim.id,
                        created_at=now,
                        created_by_stage_run_id=stage_id,
                    )
                    self.repository.save_claim_group_membership(membership)
                    memberships.append(membership)
            return tuple(item.id for item in group_by_signature.values()) + tuple(
                item.id for item in memberships
            )

        def evidence_link(stage_id: str) -> tuple[str, ...]:
            claim_by_candidate_id = {
                candidate.candidate_id: claim
                for candidate in batch.claims
                if (claim := claim_by_candidate.get(candidate.candidate_id)) is not None
            }
            for relation in batch.relations:
                claim = claim_by_candidate_id[relation.claim_candidate_id]
                evidence = evidence_by_candidate[relation.evidence_candidate_id]
                link = EvidenceLink(
                    id=stable_artifact_id(
                        "evidence-link",
                        stage_id,
                        relation.claim_candidate_id,
                        relation.evidence_candidate_id,
                        relation.relation_type.value,
                    ),
                    evidence_id=evidence.id,
                    claim_id=claim.id,
                    relation_type=relation.relation_type,
                    rationale=relation.rationale,
                    created_at=now,
                    created_by_stage_run_id=stage_id,
                )
                self.repository.save_evidence_link(link)
                links.append(link)
            return tuple(item.id for item in links)

        def independence(stage_id: str) -> tuple[str, ...]:
            for signal in batch.dependencies:
                dependency = SourceDependency(
                    id=stable_artifact_id(
                        "source-dependency",
                        stage_id,
                        signal.source_id,
                        signal.parent_source_id,
                    ),
                    source_id=signal.source_id,
                    parent_source_id=signal.parent_source_id,
                    relation_type=signal.relation_type,
                    dependency_group=signal.dependency_group,
                    independence_score=signal.independence_score,
                    reason=signal.reason,
                    signals=dict(signal.signals),
                    created_at=now,
                    created_by_stage_run_id=stage_id,
                )
                self.repository.save_source_dependency(dependency)
                dependencies.append(dependency)
            return tuple(item.id for item in dependencies)

        def contradiction(stage_id: str) -> tuple[str, ...]:
            for group in group_by_signature.values():
                claims = tuple(
                    claim
                    for claim in claim_by_candidate.values()
                    if self.repository.get_claim_group_membership(group.id, claim.id) is not None
                )
                for index, left in enumerate(claims):
                    for right in claims[index + 1 :]:
                        kind = ContradictionPolicy.classify(left, right)
                        if kind is None:
                            continue
                        item = Contradiction(
                            id=stable_artifact_id("contradiction", stage_id, left.id, right.id),
                            claim_a_id=left.id,
                            claim_b_id=right.id,
                            type=kind,
                            severity=ContradictionSeverity.HIGH
                            if kind is ContradictionType.DIRECT
                            else ContradictionSeverity.MEDIUM,
                            reason="persisted claims have incompatible normalized values",
                            status=ContradictionStatus.OPEN,
                            created_at=now,
                            created_by_stage_run_id=stage_id,
                        )
                        self.repository.save_contradiction(item)
                        contradictions.append(item)
            return tuple(item.id for item in contradictions)

        def resolve(stage_id: str) -> tuple[str, ...]:
            persisted_dependencies = tuple(self.repository.list_source_dependencies())
            for signature, group in group_by_signature.items():
                claims = tuple(
                    claim
                    for claim in claim_by_candidate.values()
                    if self.repository.get_claim_group_membership(group.id, claim.id) is not None
                )
                claim_ids = {item.id for item in claims}
                group_links = tuple(item for item in links if item.claim_id in claim_ids)
                group_contradictions = tuple(
                    item
                    for item in contradictions
                    if item.claim_a_id in claim_ids or item.claim_b_id in claim_ids
                )
                outcome = ResolutionPolicy.evaluate(
                    claims,
                    group_links,
                    group_contradictions,
                    source_for_evidence,
                    persisted_dependencies,
                )
                outcomes[group.id] = outcome
                decision = ResolutionDecision(
                    id=stable_artifact_id("resolution-decision", stage_id, signature),
                    claim_group_id=group.id,
                    canonical_statement=group.canonical_statement or group.canonical_key,
                    status=outcome.status,
                    resolution_reason=outcome.reason,
                    validity=outcome.validity,
                    created_at=now,
                    created_by_stage_run_id=stage_id,
                )
                self.repository.save_resolution_decision(decision)
                decisions.append(decision)
                for claim in claims:
                    claim_links = tuple(item for item in group_links if item.claim_id == claim.id)
                    if any(item.type is ContradictionType.DIRECT for item in group_contradictions):
                        role = ResolutionInputRole.CONTRADICTING
                    elif any(
                        item.relation_type is EvidenceLinkType.SUPPORTS for item in claim_links
                    ):
                        role = ResolutionInputRole.SUPPORTING
                    elif any(
                        item.relation_type is EvidenceLinkType.QUALIFIES for item in claim_links
                    ):
                        role = ResolutionInputRole.QUALIFYING
                    else:
                        role = ResolutionInputRole.REJECTED
                    item = ResolutionClaimInput(
                        id=stable_artifact_id(
                            "resolution-claim-input", stage_id, decision.id, claim.id
                        ),
                        resolution_decision_id=decision.id,
                        claim_id=claim.id,
                        role=role,
                        reason="persisted deterministic resolver input",
                        created_at=now,
                        created_by_stage_run_id=stage_id,
                    )
                    self.repository.save_resolution_claim_input(item)
                    claim_inputs.append(item)
                for link in group_links:
                    role = {
                        EvidenceLinkType.SUPPORTS: ResolutionInputRole.SUPPORTING,
                        EvidenceLinkType.CONTRADICTS: ResolutionInputRole.CONTRADICTING,
                        EvidenceLinkType.QUALIFIES: ResolutionInputRole.QUALIFYING,
                        EvidenceLinkType.MENTIONS: ResolutionInputRole.REJECTED,
                    }[link.relation_type]
                    item = ResolutionEvidenceInput(
                        id=stable_artifact_id(
                            "resolution-evidence-input", stage_id, decision.id, link.evidence_id
                        ),
                        resolution_decision_id=decision.id,
                        evidence_id=link.evidence_id,
                        role=role,
                        reason="persisted deterministic evidence relation",
                        created_at=now,
                        created_by_stage_run_id=stage_id,
                    )
                    self.repository.save_resolution_evidence_input(item)
                    evidence_inputs.append(item)
            return (
                tuple(item.id for item in decisions)
                + tuple(item.id for item in claim_inputs)
                + tuple(item.id for item in evidence_inputs)
            )

        def confidence(stage_id: str) -> tuple[str, ...]:
            for decision in decisions:
                group = next(
                    item
                    for item in group_by_signature.values()
                    if item.id == decision.claim_group_id
                )
                claims = tuple(
                    claim
                    for claim in claim_by_candidate.values()
                    if self.repository.get_claim_group_membership(group.id, claim.id) is not None
                )
                claim_ids = {item.id for item in claims}
                group_links = tuple(item for item in links if item.claim_id in claim_ids)
                group_contradictions = tuple(
                    item
                    for item in contradictions
                    if item.claim_a_id in claim_ids or item.claim_b_id in claim_ids
                )
                source_ids = {source_for_evidence(item.evidence_id) for item in group_links}
                source_quality = sum(
                    float(
                        (source := self.repository.get_source(item))
                        and source.metadata.get("source_quality", 0.0)
                        or 0.0
                    )
                    for item in source_ids
                ) / max(len(source_ids), 1)
                outcome = outcomes[decision.claim_group_id]
                reference_time = batch.reference_time or now
                freshness_values = []
                for link in group_links:
                    evidence = self.repository.get_evidence(link.evidence_id)
                    snapshot = (
                        self.repository.get_snapshot(evidence.snapshot_id) if evidence else None
                    )
                    if snapshot is not None:
                        freshness_values.append(
                            ConfidencePolicy.freshness(reference_time, snapshot.retrieved_at)
                        )
                freshness = min(freshness_values, default=0.0)
                supported_value_count = len(outcome.supported_values)
                agreement = 1.0 if supported_value_count == 1 else 0.0
                values = ConfidencePolicy.assess(
                    status=decision.status,
                    claims=claims,
                    links=group_links,
                    source_quality=source_quality,
                    independent_support_units=len(outcome.supporting_units),
                    agreement=agreement,
                    freshness=freshness,
                    contradictions=group_contradictions,
                )
                assessment = ConfidenceAssessment(
                    id=stable_artifact_id("confidence-assessment", stage_id, decision.id),
                    resolution_decision_id=decision.id,
                    policy_version=ConfidencePolicy.version,
                    created_at=now,
                    created_by_stage_run_id=stage_id,
                    **values,
                )
                self.repository.save_confidence_assessment(assessment)
                assessments.append(assessment)
                resolved = ResolvedClaim(
                    id=stable_artifact_id("resolved-claim", stage_id, decision.id),
                    claim_group_id=decision.claim_group_id,
                    canonical_statement=decision.canonical_statement,
                    status=decision.status,
                    confidence=assessment.score,
                    resolution_reason=decision.resolution_reason,
                    validity=decision.validity,
                    created_at=now,
                    created_by_stage_run_id=stage_id,
                    resolution_decision_id=decision.id,
                    confidence_assessment_id=assessment.id,
                )
                self.repository.save_resolved_claim(resolved)
                resolved_claims.append(resolved)
            return tuple(item.id for item in assessments) + tuple(
                item.id for item in resolved_claims
            )

        def atom_build(stage_id: str) -> tuple[str, ...]:
            for resolved, assessment, decision in zip(
                resolved_claims, assessments, decisions, strict=True
            ):
                group = next(
                    item
                    for item in group_by_signature.values()
                    if item.id == decision.claim_group_id
                )
                outcome = outcomes[decision.claim_group_id]
                status = AtomPolicy.status(
                    resolved.status, assessment.evidence_floor_met, assessment.score
                )
                atom = KnowledgeAtom(
                    id=stable_artifact_id("knowledge-atom", stage_id, resolved.id),
                    resolved_claim_id=resolved.id,
                    statement=resolved.canonical_statement,
                    confidence=resolved.confidence,
                    qualifiers=group.qualifiers,
                    created_at=now,
                    created_by_stage_run_id=stage_id,
                    subject=group.subject,
                    predicate=group.predicate,
                    object=outcome.selected_value,
                    status=status,
                    validity=resolved.validity,
                )
                self.repository.save_knowledge_atom(atom)
                atoms.append(atom)
            return tuple(item.id for item in atoms)

        execute_stage("evidence_extract", evidence_extract)
        execute_stage("claim_extract", claim_extract)
        execute_stage("normalize", normalize)
        execute_stage("evidence_link", evidence_link)
        execute_stage("independence", independence)
        execute_stage("contradiction", contradiction)
        execute_stage("resolve", resolve)
        execute_stage("confidence", confidence)
        execute_stage("atom_build", atom_build)

        if not pipeline_replay or pipeline.status is PipelineRunStatus.STARTED:
            pipeline = replace(
                pipeline,
                status=PipelineRunStatus.SUCCEEDED,
                finished_at=now,
                output_ref=output_manifests[-1].ref,
            )
            self.repository.save_pipeline_run(pipeline)
        source_ids = tuple(sorted({item.source_id for item in snapshots}))
        sources = tuple(
            source
            for source_id in source_ids
            if (source := self.repository.get_source(source_id)) is not None
        )
        signatures = tuple(
            sorted(
                (
                    group_signature_by_id[decision.claim_group_id],
                    decision.status.value,
                    decision.validity or "",
                    atom.status.value,
                    f"{atom.confidence or 0.0:.6f}",
                )
                for decision, atom in zip(decisions, atoms, strict=True)
            )
        )
        metrics = {
            "effective_independence_count": max(
                (len(outcome.supporting_units) for outcome in outcomes.values()), default=0
            ),
            "semantic_signature": signatures,
        }
        return DeterministicRefineryResult(
            fixture_id=fixture_id,
            pipeline_run=pipeline,
            stage_runs=tuple(stage_runs),
            manifests=tuple(output_manifests),
            input_manifests=tuple(input_manifests),
            manifest_store=self.manifest_store,
            snapshots=snapshots,
            sources=sources,
            evidences=tuple(evidence_by_candidate.values()),
            claims=tuple(claim_by_candidate.values()),
            claim_groups=tuple(group_by_signature.values()),
            memberships=tuple(memberships),
            evidence_links=tuple(links),
            dependencies=tuple(dependencies),
            contradictions=tuple(contradictions),
            decisions=tuple(decisions),
            claim_inputs=tuple(claim_inputs),
            evidence_inputs=tuple(evidence_inputs),
            assessments=tuple(assessments),
            resolved_claims=tuple(resolved_claims),
            atoms=tuple(atoms),
            semantic_signature=signatures,
            metrics=metrics,
        )


__all__ = [
    "AtomPolicy",
    "CANONICAL_STAGE_NAMES",
    "ConfidencePolicy",
    "ContradictionPolicy",
    "DETERMINISTIC_PIPELINE_VERSION",
    "DeterministicRefinery",
    "DeterministicRefineryResult",
    "IndependencePolicy",
    "NormalizationPolicy",
    "ResolutionPolicy",
]
