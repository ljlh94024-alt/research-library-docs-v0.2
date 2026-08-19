# ADR-0009: Contradiction 与 Claim Resolution

**Status:** Accepted  
**Date:** 2026-08-19

## Context

系统不能把冲突隐藏在摘要里，也不能把历史变化误判为矛盾。需要一条确定的候选生成、验证和解析路径。

## Decision

Contradiction 分两步：结构规则产生候选，Verifier 判断是否真实矛盾；Resolution 在 ClaimGroup 层进行，输出 resolved/unresolved/conflicting/insufficient_evidence/historical_change。

候选规则优先 same subject + predicate + incompatible values，同时比较 temporal scope、qualifiers、units 与 context。Resolver 使用证据直接程度、来源质量、独立性、freshness 与矛盾严重度。LLM 负责解释和边界判断，但不能单独决定最终 confidence。

## Alternatives Considered

**任何 object 不同都算矛盾**：误报历史变化与条件差异。

**让 LLM 一次性判断所有 Claims**：可解释性与重现性差。

## Consequences

冲突成为一等数据对象，可保留 unresolved 状态。代价是 Pipeline 多一个验证阶段，但能避免知识库“强行统一”。

## Implementation Rules

Resolution 不得删除失败候选；历史事实应通过 validity 表达；高严重度 unresolved contradiction 默认阻止生成高置信 active Atom。
