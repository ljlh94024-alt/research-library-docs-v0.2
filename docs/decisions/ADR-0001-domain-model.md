# ADR-0001: 核心领域模型

**Status:** Accepted  
**Date:** 2026-08-19

## Context

Research Library 的核心不是“文档 + chunk + embedding”，而是把来源逐步提炼成可验证、可追溯、可更新的知识。领域模型必须明确区分 Source、SourceSnapshot、Evidence、Claim、ResolvedClaim 与 KnowledgeAtom，并允许同一 Claim 被多个 Evidence 支持或反驳。

## Decision

采用显式领域对象与关系：Source 1:N SourceSnapshot；SourceSnapshot 1:N Evidence；Evidence N:M Claim；Claim N:1 ClaimGroup；ClaimGroup 1:N ResolvedClaim；ResolvedClaim 1:N KnowledgeAtom。Claim 之间可建立 Contradiction。

### 核心对象

- Source：逻辑来源，字段包括 id、source_type、canonical_uri、title、publisher、metadata、created_at。
- SourceSnapshot：不可变快照，包含 source_id、retrieved_at、content_hash、content_ref、mime_type、metadata。
- Evidence：快照中的证据片段，包含 text、locator、context、extraction_method。
- Claim：独立事实候选，包含 subject、predicate、object、statement、qualifiers、temporal_scope、extraction_confidence。
- EvidenceLink：Claim 与 Evidence 的 supports、contradicts、qualifies、mentions 关系。
- ClaimGroup：将语义上回答同一问题的 Claim 聚合。
- Contradiction：显式记录 claim_a、claim_b、type、severity、reason、status。
- ResolvedClaim：当前解析结果，包含 canonical_statement、status、confidence、resolution_reason、validity。
- KnowledgeAtom：面向上层的最小知识单元。

## Alternatives Considered

**Document + Chunk**：拒绝作为核心模型，因为难以表达 Claim 生命周期、冲突、事实归一和长期维护。

**完整 Knowledge Graph**：暂不采用，Ontology 成本高，会拖慢 MVP。

## Consequences

优点是 provenance 清晰、支持多来源、冲突、重算与 temporal knowledge；代价是比普通 RAG 更复杂，需要维护 ClaimGroup 与 EvidenceLink。

## Implementation Rules

不得合并 SourceSnapshot 与 Evidence、Evidence 与 Claim、Claim 与 ResolvedClaim、ResolvedClaim 与 KnowledgeAtom。KnowledgeAtom 的正式 provenance 不得跳过 Claim / Evidence。
