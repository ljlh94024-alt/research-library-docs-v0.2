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
    RefineryStage,
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


def test_phase1_contracts_copy_collections_to_immutable_tuples(repository) -> None:
    source_ids = ["source-a", "source-b"]
    evidence_ids = ["evidence-a"]
    contract = EvidenceLinkInput(source_ids, evidence_ids)
    source_ids.append("source-c")
    evidence_ids.clear()
    assert contract.claim_ids == ("source-a", "source-b")
    assert contract.evidence_ids == ("evidence-a",)
    assert isinstance(contract.claim_ids, tuple)
    assert isinstance(contract.evidence_ids, tuple)
    assert EvidenceExtractInput([]).snapshot_ids == ()


@pytest.mark.parametrize(
    "factory",
    (
        lambda value: EvidenceExtractInput(value),
        lambda value: ClaimExtractOutput(value),
        lambda value: NormalizeOutput(value),
        lambda value: IndependenceOutput(value),
        lambda value: ResolveOutput(value),
        lambda value: AtomBuildInput(value),
    ),
)
def test_phase1_contracts_reject_strings_and_blank_ids(factory) -> None:
    with pytest.raises(TypeError, match="not a string"):
        factory("bare-id")
    with pytest.raises(ValueError, match="non-empty"):
        factory([" "])


def test_refinery_stage_protocol_supports_structural_fake_stage(repository) -> None:
    class FakeStage:
        name = "fake"
        version = "test"

        def run(self, context: StageContext, input: EvidenceExtractInput) -> EvidenceExtractOutput:
            assert context.stage_run_id == "stage"
            return EvidenceExtractOutput(input.snapshot_ids)

    fake = FakeStage()
    assert isinstance(fake, RefineryStage)
    output = fake.run(StageContext("pipeline", "stage", repository), EvidenceExtractInput(["id"]))
    assert output.evidence_ids == ("id",)
