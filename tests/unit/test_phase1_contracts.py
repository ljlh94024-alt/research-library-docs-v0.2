from dataclasses import FrozenInstanceError, is_dataclass

import pytest

from research_library.refinery.contracts import (
    CANONICAL_STAGE_NAMES,
    AtomBuildInput,
    AtomBuildOutput,
    ClaimExtractInput,
    ClaimExtractOutput,
    ConfidenceInput,
    ConfidenceOutput,
    ContradictionInput,
    ContradictionOutput,
    EvidenceExtractInput,
    EvidenceExtractOutput,
    EvidenceLinkInput,
    EvidenceLinkOutput,
    IndependenceInput,
    IndependenceOutput,
    NormalizeInput,
    NormalizeOutput,
    ResolveInput,
    ResolveOutput,
    StageContext,
)


def test_phase1_contracts_are_frozen_and_cover_nine_stages(repository) -> None:
    assert CANONICAL_STAGE_NAMES == (
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
    contracts = (
        EvidenceExtractInput(("snapshot",)),
        EvidenceExtractOutput(("evidence",)),
        ClaimExtractInput(("evidence",)),
        ClaimExtractOutput(("claim",)),
        NormalizeInput(("claim",)),
        NormalizeOutput(("group",)),
        EvidenceLinkInput(("claim",), ("evidence",)),
        EvidenceLinkOutput(("link",)),
        IndependenceInput(("source",)),
        IndependenceOutput(("dependency",)),
        ContradictionInput(("group",)),
        ContradictionOutput(("contradiction",)),
        ResolveInput(("group",), ("contradiction",)),
        ResolveOutput(("decision",)),
        ConfidenceInput(("decision",)),
        ConfidenceOutput(("assessment",), ("resolved",)),
        AtomBuildInput(("resolved",)),
        AtomBuildOutput(("atom",)),
        StageContext("pipeline", "stage", repository),
    )
    assert all(is_dataclass(item) for item in contracts)
    with pytest.raises(FrozenInstanceError):
        contracts[0].snapshot_ids = ("changed",)
