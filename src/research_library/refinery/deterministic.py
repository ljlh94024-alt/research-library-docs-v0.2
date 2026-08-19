"""Phase 1B deterministic nine-stage knowledge refinery."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import UTC
from typing import Any

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

from .backend import FixtureSemanticBackend
from .fixtures import FixtureClaimSpec
from .manifests import StageManifest, stable_artifact_id

DETERMINISTIC_PIPELINE_VERSION = "phase1b-deterministic-v1"
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


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class NormalizationPolicy:
    version = "normalization-v1"

    @staticmethod
    def canonical_key(fixture_id: str, claim: FixtureClaimSpec) -> str:
        return stable_artifact_id("claim-group-key", fixture_id, claim.group_key)

    @staticmethod
    def normalize_statement(statement: str) -> str:
        return " ".join(statement.lower().split()).rstrip(".")


class IndependencePolicy:
    version = "independence-v1"

    @staticmethod
    def effective_group(source: Source, fixture_source: Any) -> str:
        return fixture_source.dependency_group or source.id

    @staticmethod
    def count(source_keys: set[str], spec_by_key: dict[str, Any]) -> int:
        return len({spec_by_key[item].dependency_group or item for item in source_keys})


class ContradictionPolicy:
    version = "contradiction-v1"

    @staticmethod
    def incompatible(left: Claim, right: Claim) -> bool:
        return (
            left.subject is not None
            and left.subject == right.subject
            and left.predicate is not None
            and left.predicate == right.predicate
            and left.object is not None
            and right.object is not None
            and left.object != right.object
            and left.temporal_scope == right.temporal_scope
        )


class ResolutionPolicy:
    version = "resolution-v1"

    @staticmethod
    def status(
        claims: tuple[Claim, ...],
        links: tuple[EvidenceLink, ...],
        contradictions: tuple[Contradiction, ...],
    ) -> tuple[ResolvedClaimStatus, str | None, str]:
        if contradictions:
            return (
                ResolvedClaimStatus.CONFLICTING,
                None,
                "direct contradiction remains open; publication is withheld",
            )
        if len({claim.temporal_scope for claim in claims}) > 1:
            return (
                ResolvedClaimStatus.HISTORICAL_CHANGE,
                "historical",
                "claims differ by temporal scope",
            )
        relations = {link.relation_type for link in links}
        if (
            EvidenceLinkType.SUPPORTS not in relations
            and EvidenceLinkType.QUALIFIES not in relations
        ):
            return (
                ResolvedClaimStatus.INSUFFICIENT_EVIDENCE,
                None,
                "no supporting or qualifying evidence",
            )
        if EvidenceLinkType.SUPPORTS not in relations:
            return (
                ResolvedClaimStatus.RESOLVED,
                "conditional",
                "qualifying evidence is retained as conditional",
            )
        return ResolvedClaimStatus.RESOLVED, None, "independent supporting evidence agrees"


class ConfidencePolicy:
    version = "confidence-v1"

    @staticmethod
    def assess(
        claims: tuple[Claim, ...],
        links: tuple[EvidenceLink, ...],
        source_quality: float,
        effective_independence_count: int,
        contradictions: tuple[Contradiction, ...],
    ) -> dict[str, Any]:
        directness_values = {
            EvidenceLinkType.SUPPORTS: 1.0,
            EvidenceLinkType.QUALIFIES: 0.6,
            EvidenceLinkType.MENTIONS: 0.2,
            EvidenceLinkType.CONTRADICTS: 0.0,
        }
        directness = sum(directness_values[link.relation_type] for link in links) / max(
            len(links), 1
        )
        independence = _clamp(effective_independence_count / 2)
        extraction = sum(claim.extraction_confidence or 0.0 for claim in claims) / max(
            len(claims), 1
        )
        has_support = any(link.relation_type is EvidenceLinkType.SUPPORTS for link in links)
        floor = (
            bool(links)
            and (
                has_support
                or any(link.relation_type is EvidenceLinkType.QUALIFIES for link in links)
            )
            and not contradictions
        )
        penalty = 0.4 if contradictions else 0.0
        agreement = 0.0 if contradictions else 1.0
        score = _clamp(
            (source_quality + directness + independence + agreement + 1.0 + extraction) / 6
            - penalty
        )
        publish_cap = 0.2 if contradictions else None
        if publish_cap is not None:
            score = min(score, publish_cap)
        return {
            "source_quality": _clamp(source_quality),
            "evidence_directness": _clamp(directness),
            "source_independence": independence,
            "agreement": agreement,
            "freshness": 1.0,
            "extraction_confidence": _clamp(extraction),
            "contradiction_penalty": penalty,
            "publish_cap": publish_cap,
            "evidence_floor_met": floor,
            "score": score,
            "reasons": {
                "policy": [
                    "deterministic confidence policy v1",
                    f"effective_independence_count={effective_independence_count}",
                ],
                "evidence": [f"links={len(links)}", f"supporting={int(has_support)}"],
                "contradiction": [
                    "open contradiction" if contradictions else "no open contradiction"
                ],
            },
        }


class AtomPolicy:
    version = "atom-v1"

    @staticmethod
    def status(status: ResolvedClaimStatus, evidence_floor_met: bool) -> KnowledgeAtomStatus:
        return (
            KnowledgeAtomStatus.ACTIVE
            if status is ResolvedClaimStatus.RESOLVED and evidence_floor_met
            else KnowledgeAtomStatus.WITHHELD
        )


@dataclass(frozen=True, slots=True)
class DeterministicRefineryResult:
    fixture_id: str
    pipeline_run: PipelineRun
    stage_runs: tuple[StageRun, ...]
    manifests: tuple[StageManifest, ...]
    sources: tuple[Source, ...] = ()
    snapshots: tuple[SourceSnapshot, ...] = ()
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
            self.sources,
            self.snapshots,
            self.evidences,
            self.claims,
            self.claim_groups,
            self.evidence_links,
            self.dependencies,
            self.contradictions,
            self.decisions,
            self.assessments,
            self.resolved_claims,
            self.atoms,
        )
        return tuple(item.id for values in collections for item in values)

    @property
    def manifest_ids(self) -> tuple[str, ...]:
        return tuple(item.manifest_id for item in self.manifests)


class DeterministicRefinery:
    """Execute the complete offline Phase 1B pipeline against a repository."""

    def __init__(
        self,
        repository: Repository,
        backend: FixtureSemanticBackend | None = None,
        *,
        pipeline_version: str = DETERMINISTIC_PIPELINE_VERSION,
    ) -> None:
        if not pipeline_version.startswith("phase1b"):
            raise ValueError("Phase 1B pipeline version must start with phase1b")
        self.repository = repository
        self.backend = backend or FixtureSemanticBackend()
        self.pipeline_version = pipeline_version

    def run(self, fixture_id: str, *, run_key: str = "golden") -> DeterministicRefineryResult:
        fixture = self.backend.get_fixture(fixture_id)
        now = fixture.created_at.astimezone(UTC)
        pipeline_id = stable_artifact_id("pipeline-run", fixture_id, self.pipeline_version, run_key)
        input_manifest = f"fixture:{fixture_id}"
        pipeline = PipelineRun(
            id=pipeline_id,
            pipeline_version=self.pipeline_version,
            status=PipelineRunStatus.STARTED,
            started_at=now,
            input_ref=input_manifest,
            metadata={"fixture_id": fixture_id, "backend": "fixture"},
        )
        existing_pipeline = self.repository.get_pipeline_run(pipeline_id)
        pipeline_replay = existing_pipeline is not None
        if existing_pipeline is not None:
            if existing_pipeline.status is not PipelineRunStatus.SUCCEEDED:
                raise RuntimeError(f"cannot replay non-successful pipeline: {pipeline_id}")
            pipeline = existing_pipeline
        else:
            self.repository.save_pipeline_run(pipeline)
        stage_runs: list[StageRun] = []
        manifests: list[StageManifest] = []
        prior_ids: tuple[str, ...] = ()

        source_specs = {item.key: item for item in fixture.sources}
        source_ids = {
            key: stable_artifact_id("source", fixture_id, key, spec.canonical_uri)
            for key, spec in source_specs.items()
        }
        snapshot_specs = {item.key: item for item in fixture.snapshots}
        snapshot_ids = {
            key: stable_artifact_id("snapshot", fixture_id, key, _content_hash(spec.content))
            for key, spec in snapshot_specs.items()
        }
        evidence_specs = {item.key: item for item in fixture.evidences}
        evidence_ids = {
            key: stable_artifact_id("evidence", fixture_id, key, spec.text)
            for key, spec in evidence_specs.items()
        }
        claim_specs = {item.key: item for item in fixture.claims}
        claim_ids = {
            key: stable_artifact_id("claim", fixture_id, key, spec.statement)
            for key, spec in claim_specs.items()
        }
        claim_key_by_id = {value: key for key, value in claim_ids.items()}
        group_ids = {
            key: stable_artifact_id("claim-group", fixture_id, key)
            for key in {item.group_key for item in fixture.claims}
        }
        source_by_id: dict[str, Source] = {}
        snapshots_by_key: dict[str, SourceSnapshot] = {}
        evidence_by_key: dict[str, Evidence] = {}
        claims_by_key: dict[str, Claim] = {}
        groups_by_key: dict[str, ClaimGroup] = {}
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

        def stage(
            stage_name: str,
            output_ids: tuple[str, ...],
            action: Any,
            *,
            metadata: dict[str, str] | None = None,
        ) -> None:
            nonlocal prior_ids
            stage_id = stable_artifact_id("stage-run", pipeline_id, stage_name)
            in_manifest = StageManifest(
                stage_name,
                self.pipeline_version,
                prior_ids,
                (),
                {"fixture_id": fixture_id, **(metadata or {})},
            )
            started = StageRun(
                id=stage_id,
                pipeline_run_id=pipeline_id,
                stage_name=stage_name,
                stage_version=self.pipeline_version,
                status=StageRunStatus.STARTED,
                input_ref=in_manifest.ref,
                started_at=now,
                model="fixture-semantic-backend",
                provider="offline",
            )
            existing_stage = self.repository.get_stage_run(stage_id)
            if existing_stage is not None:
                if existing_stage.status is not StageRunStatus.SUCCEEDED:
                    raise RuntimeError(f"cannot replay non-successful stage: {stage_id}")
                started = existing_stage
            else:
                self.repository.save_stage_run(started)
            action(stage_id)
            out_manifest = StageManifest(
                stage_name,
                self.pipeline_version,
                prior_ids,
                output_ids,
                {"fixture_id": fixture_id, **(metadata or {})},
            )
            succeeded = replace(
                started,
                status=StageRunStatus.SUCCEEDED,
                finished_at=now,
                output_ref=out_manifest.ref,
            )
            if existing_stage is None:
                self.repository.save_stage_run(succeeded)
            else:
                succeeded = existing_stage
            stage_runs.append(succeeded)
            manifests.append(out_manifest)
            prior_ids = tuple(output_ids)

        def extract_evidence(stage_id: str) -> None:
            for spec in fixture.sources:
                source = Source(
                    id=source_ids[spec.key],
                    source_type=spec.source_type,
                    canonical_uri=spec.canonical_uri,
                    title=spec.title,
                    publisher=spec.publisher,
                    metadata={
                        **spec.metadata,
                        "fixture_key": spec.key,
                        "source_quality": spec.source_quality,
                        "dependency_group": spec.dependency_group,
                    },
                    created_at=now,
                )
                self.repository.save_source(source)
                source_by_id[spec.key] = source
            for spec in fixture.snapshots:
                snapshot = self.repository.create_snapshot(
                    source_ids[spec.source_key],
                    spec.content,
                    snapshot_id=snapshot_ids[spec.key],
                    retrieved_at=spec.retrieved_at,
                    mime_type=spec.mime_type,
                    metadata={**spec.metadata, "fixture_key": spec.key},
                    created_by_stage_run_id=stage_id,
                )
                snapshots_by_key[spec.key] = snapshot
            for spec in fixture.evidences:
                evidence = Evidence(
                    id=evidence_ids[spec.key],
                    snapshot_id=snapshot_ids[spec.snapshot_key],
                    text=spec.text,
                    locator=spec.locator,
                    context=spec.context,
                    extraction_method=spec.extraction_method,
                    created_at=now,
                    created_by_stage_run_id=stage_id,
                )
                self.repository.save_evidence(evidence)
                evidence_by_key[spec.key] = evidence

        def extract_claims(stage_id: str) -> None:
            for spec in fixture.claims:
                claim = Claim(
                    id=claim_ids[spec.key],
                    statement=spec.statement,
                    subject=spec.subject,
                    predicate=spec.predicate,
                    object=spec.object,
                    qualifiers=spec.qualifiers,
                    temporal_scope=spec.temporal_scope,
                    extraction_confidence=spec.extraction_confidence,
                    created_at=now,
                    created_by_stage_run_id=stage_id,
                )
                self.repository.save_claim(claim)
                claims_by_key[spec.key] = claim

        def normalize(stage_id: str) -> None:
            for group_key in sorted(group_ids):
                member = next(item for item in fixture.claims if item.group_key == group_key)
                claim_group = ClaimGroup(
                    id=group_ids[group_key],
                    canonical_key=NormalizationPolicy.canonical_key(fixture_id, member),
                    canonical_statement=member.group_statement,
                    subject=member.subject,
                    predicate=member.predicate,
                    qualifiers=member.qualifiers,
                    temporal_scope=member.temporal_scope,
                    created_at=now,
                    created_by_stage_run_id=stage_id,
                )
                self.repository.save_claim_group(claim_group)
                groups_by_key[group_key] = claim_group
                for claim_spec in sorted(
                    (item for item in fixture.claims if item.group_key == group_key),
                    key=lambda item: item.key,
                ):
                    membership = ClaimGroupMembership(
                        claim_group_id=claim_group.id,
                        claim_id=claim_ids[claim_spec.key],
                        created_at=now,
                        created_by_stage_run_id=stage_id,
                    )
                    self.repository.save_claim_group_membership(membership)
                    memberships.append(membership)

        def link_evidence(stage_id: str) -> None:
            for claim_spec in fixture.claims:
                for evidence_key in claim_spec.evidence_keys:
                    link = EvidenceLink(
                        id=stable_artifact_id(
                            "evidence-link",
                            fixture_id,
                            claim_spec.key,
                            evidence_key,
                            claim_spec.relation_for(evidence_key).value,
                        ),
                        evidence_id=evidence_ids[evidence_key],
                        claim_id=claim_ids[claim_spec.key],
                        relation_type=claim_spec.relation_for(evidence_key),
                        rationale=(
                            "fixture semantic relation: "
                            f"{claim_spec.relation_for(evidence_key).value}"
                        ),
                        created_at=now,
                        created_by_stage_run_id=stage_id,
                    )
                    self.repository.save_evidence_link(link)
                    links.append(link)

        def assess_independence(stage_id: str) -> None:
            for spec in fixture.sources:
                if spec.parent_key is None:
                    continue
                dependency = SourceDependency(
                    id=stable_artifact_id(
                        "source-dependency",
                        fixture_id,
                        spec.key,
                        spec.parent_key,
                        spec.dependency_relation.value,
                    ),
                    source_id=source_ids[spec.key],
                    parent_source_id=source_ids[spec.parent_key],
                    relation_type=spec.dependency_relation,
                    dependency_group=spec.dependency_group,
                    independence_score=0.0,
                    reason="fixture declares shared origin",
                    signals={"fixture_key": spec.key},
                    created_at=now,
                    created_by_stage_run_id=stage_id,
                )
                self.repository.save_source_dependency(dependency)
                dependencies.append(dependency)

        def detect_contradictions(stage_id: str) -> None:
            for group_key in sorted(group_ids):
                claims = [
                    claims_by_key[item.key]
                    for item in fixture.claims
                    if item.group_key == group_key
                ]
                for index, left in enumerate(claims):
                    for right in claims[index + 1 :]:
                        if not ContradictionPolicy.incompatible(left, right):
                            continue
                        item = Contradiction(
                            id=stable_artifact_id("contradiction", fixture_id, left.id, right.id),
                            claim_a_id=left.id,
                            claim_b_id=right.id,
                            type=ContradictionType.DIRECT,
                            severity=ContradictionSeverity.HIGH,
                            reason="same subject and predicate have incompatible values",
                            status=ContradictionStatus.OPEN,
                            created_at=now,
                            created_by_stage_run_id=stage_id,
                        )
                        self.repository.save_contradiction(item)
                        contradictions.append(item)

        def resolve(stage_id: str) -> None:
            for group_key in sorted(group_ids):
                group = groups_by_key[group_key]
                claims = tuple(
                    claims_by_key[item.key]
                    for item in fixture.claims
                    if item.group_key == group_key
                )
                claim_set = {claim.id for claim in claims}
                group_links = tuple(item for item in links if item.claim_id in claim_set)
                group_contradictions = tuple(
                    item
                    for item in contradictions
                    if item.claim_a_id in claim_set or item.claim_b_id in claim_set
                )
                status, validity, reason = ResolutionPolicy.status(
                    claims, group_links, group_contradictions
                )
                decision = ResolutionDecision(
                    id=stable_artifact_id("resolution-decision", fixture_id, group_key),
                    claim_group_id=group.id,
                    canonical_statement=group.canonical_statement or group.canonical_key,
                    status=status,
                    resolution_reason=reason,
                    validity=validity,
                    created_at=now,
                    created_by_stage_run_id=stage_id,
                )
                self.repository.save_resolution_decision(decision)
                decisions.append(decision)
                for claim in claims:
                    claim_role = ResolutionInputRole.SUPPORTING
                    if any(
                        item.claim_a_id == claim.id or item.claim_b_id == claim.id
                        for item in group_contradictions
                    ):
                        claim_role = ResolutionInputRole.CONTRADICTING
                    claim_input = ResolutionClaimInput(
                        id=stable_artifact_id(
                            "resolution-claim-input",
                            fixture_id,
                            decision.id,
                            claim.id,
                            claim_role.value,
                        ),
                        resolution_decision_id=decision.id,
                        claim_id=claim.id,
                        role=claim_role,
                        reason="deterministic resolution input",
                        created_at=now,
                        created_by_stage_run_id=stage_id,
                    )
                    self.repository.save_resolution_claim_input(claim_input)
                    claim_inputs.append(claim_input)
                for link in group_links:
                    role = {
                        EvidenceLinkType.SUPPORTS: ResolutionInputRole.SUPPORTING,
                        EvidenceLinkType.CONTRADICTS: ResolutionInputRole.CONTRADICTING,
                        EvidenceLinkType.QUALIFIES: ResolutionInputRole.QUALIFYING,
                        EvidenceLinkType.MENTIONS: ResolutionInputRole.REJECTED,
                    }[link.relation_type]
                    evidence_input = ResolutionEvidenceInput(
                        id=stable_artifact_id(
                            "resolution-evidence-input",
                            fixture_id,
                            decision.id,
                            link.evidence_id,
                            role.value,
                        ),
                        resolution_decision_id=decision.id,
                        evidence_id=link.evidence_id,
                        role=role,
                        reason="deterministic evidence relation",
                        created_at=now,
                        created_by_stage_run_id=stage_id,
                    )
                    self.repository.save_resolution_evidence_input(evidence_input)
                    evidence_inputs.append(evidence_input)

        def score_confidence(stage_id: str) -> None:
            for decision in decisions:
                claims = tuple(
                    claim
                    for claim in claims_by_key.values()
                    if any(
                        item.claim_id == claim.id and item.resolution_decision_id == decision.id
                        for item in claim_inputs
                    )
                )
                claim_set = {claim.id for claim in claims}
                group_links = tuple(item for item in links if item.claim_id in claim_set)
                group_contradictions = tuple(
                    item
                    for item in contradictions
                    if item.claim_a_id in claim_set or item.claim_b_id in claim_set
                )
                source_keys = {
                    snapshot_specs[evidence_specs[evidence_key].snapshot_key].source_key
                    for claim in claims
                    for evidence_key in claim_specs[claim_key_by_id[claim.id]].evidence_keys
                }
                effective_count = IndependencePolicy.count(source_keys, source_specs)
                quality = sum(source_specs[key].source_quality for key in source_keys) / max(
                    len(source_keys), 1
                )
                values = ConfidencePolicy.assess(
                    claims, group_links, quality, effective_count, group_contradictions
                )
                assessment = ConfidenceAssessment(
                    id=stable_artifact_id("confidence-assessment", fixture_id, decision.id),
                    resolution_decision_id=decision.id,
                    policy_version=ConfidencePolicy.version,
                    created_by_stage_run_id=stage_id,
                    created_at=now,
                    **values,
                )
                self.repository.save_confidence_assessment(assessment)
                assessments.append(assessment)
                resolved = ResolvedClaim(
                    id=stable_artifact_id("resolved-claim", fixture_id, decision.claim_group_id),
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

        def build_atoms(stage_id: str) -> None:
            for resolved, assessment, decision in zip(
                resolved_claims, assessments, decisions, strict=True
            ):
                status = AtomPolicy.status(resolved.status, assessment.evidence_floor_met)
                group = next(
                    item for item in groups_by_key.values() if item.id == resolved.claim_group_id
                )
                group_key = next(
                    key for key, value in groups_by_key.items() if value.id == group.id
                )
                group_claim = next(item for item in fixture.claims if item.group_key == group_key)
                atom = KnowledgeAtom(
                    id=stable_artifact_id("knowledge-atom", fixture_id, resolved.id),
                    resolved_claim_id=resolved.id,
                    statement=resolved.canonical_statement,
                    confidence=resolved.confidence,
                    qualifiers=group.qualifiers,
                    created_at=now,
                    created_by_stage_run_id=stage_id,
                    subject=group.subject,
                    predicate=group.predicate,
                    object=group_claim.object,
                    status=status,
                    validity=resolved.validity,
                )
                self.repository.save_knowledge_atom(atom)
                atoms.append(atom)

        stage(
            "evidence_extract",
            tuple(source_ids.values())
            + tuple(snapshot_ids.values())
            + tuple(evidence_ids.values()),
            extract_evidence,
        )
        stage("claim_extract", tuple(claim_ids.values()), extract_claims)
        stage(
            "normalize",
            tuple(group_ids.values())
            + tuple(
                f"{group_ids[item.group_key]}:{claim_ids[item.key]}" for item in fixture.claims
            ),
            normalize,
        )
        stage(
            "evidence_link",
            tuple(
                stable_artifact_id(
                    "evidence-link",
                    fixture_id,
                    claim.key,
                    evidence_key,
                    claim.relation_for(evidence_key).value,
                )
                for claim in fixture.claims
                for evidence_key in claim.evidence_keys
            ),
            link_evidence,
        )
        stage(
            "independence",
            tuple(
                stable_artifact_id(
                    "source-dependency",
                    fixture_id,
                    item.key,
                    item.parent_key,
                    item.dependency_relation.value,
                )
                for item in fixture.sources
                if item.parent_key
            ),
            assess_independence,
        )
        stage(
            "contradiction",
            tuple(
                stable_artifact_id(
                    "contradiction", fixture_id, claim_ids[left.key], claim_ids[right.key]
                )
                for index, left in enumerate(fixture.claims)
                for right in fixture.claims[index + 1 :]
                if left.group_key == right.group_key and left.object != right.object
            ),
            detect_contradictions,
        )
        stage(
            "resolve",
            tuple(
                stable_artifact_id("resolution-decision", fixture_id, key)
                for key in sorted(group_ids)
            ),
            resolve,
        )
        stage(
            "confidence",
            tuple(
                stable_artifact_id(
                    "confidence-assessment",
                    fixture_id,
                    stable_artifact_id("resolution-decision", fixture_id, key),
                )
                for key in sorted(group_ids)
            )
            + tuple(
                stable_artifact_id("resolved-claim", fixture_id, group_ids[key])
                for key in sorted(group_ids)
            ),
            score_confidence,
        )
        stage(
            "atom_build",
            tuple(
                stable_artifact_id(
                    "knowledge-atom",
                    fixture_id,
                    stable_artifact_id("resolved-claim", fixture_id, group_ids[key]),
                )
                for key in sorted(group_ids)
            ),
            build_atoms,
        )
        final_manifest = manifests[-1]
        pipeline = replace(
            pipeline,
            status=PipelineRunStatus.SUCCEEDED,
            finished_at=now,
            output_ref=final_manifest.ref,
        )
        if not pipeline_replay:
            self.repository.save_pipeline_run(pipeline)
        all_source_keys = {
            snapshot_specs[evidence_specs[evidence_key].snapshot_key].source_key
            for claim in fixture.claims
            for evidence_key in claim.evidence_keys
        }
        return DeterministicRefineryResult(
            fixture_id=fixture_id,
            pipeline_run=pipeline,
            stage_runs=tuple(stage_runs),
            manifests=tuple(manifests),
            sources=tuple(source_by_id.values()),
            snapshots=tuple(snapshots_by_key.values()),
            evidences=tuple(evidence_by_key.values()),
            claims=tuple(claims_by_key.values()),
            claim_groups=tuple(groups_by_key.values()),
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
            metrics={
                "effective_independence_count": IndependencePolicy.count(
                    all_source_keys, source_specs
                ),
                "fixture_expected": dict(fixture.expected),
            },
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
