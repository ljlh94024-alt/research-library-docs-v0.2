from research_library.domain import (
    Claim,
    ClaimGroup,
    Evidence,
    EvidenceLink,
    KnowledgeAtom,
    ResolvedClaim,
    Source,
    SourceType,
)


def test_knowledge_atom_round_trips_full_provenance(repository) -> None:
    source = repository.save_source(
        Source(
            source_type=SourceType.PAPER,
            canonical_uri="https://example.test/paper",
            title="Example",
        )
    )
    snapshot = repository.create_snapshot(
        source.id, "The paper says the sky is blue.", mime_type="text/plain"
    )
    evidence = repository.save_evidence(
        Evidence(
            snapshot_id=snapshot.id,
            text="the sky is blue",
            locator="p. 1",
            extraction_method="fixture",
        )
    )
    claim = repository.save_claim(
        Claim(statement="The sky is blue", subject="sky", predicate="is", object="blue")
    )
    group = repository.save_claim_group(ClaimGroup(canonical_key="sky-is-blue"))
    repository.add_claim_to_group(group.id, claim.id)
    repository.save_evidence_link(
        EvidenceLink(evidence_id=evidence.id, claim_id=claim.id, rationale="direct quote")
    )
    resolved = repository.save_resolved_claim(
        ResolvedClaim(
            claim_group_id=group.id, canonical_statement="The sky is blue", confidence=0.9
        )
    )
    atom = repository.save_knowledge_atom(
        KnowledgeAtom(resolved_claim_id=resolved.id, statement="The sky is blue", confidence=0.9)
    )

    chain = repository.get_provenance(atom.id)
    assert chain.atom.id == atom.id
    assert chain.resolved_claim.id == resolved.id
    assert chain.claim.id == claim.id
    assert chain.evidence.id == evidence.id
    assert chain.snapshot.id == snapshot.id
    assert chain.source.id == source.id
    assert repository.read_snapshot(snapshot.id) == b"The paper says the sky is blue."
