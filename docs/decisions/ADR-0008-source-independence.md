# ADR-0008: Source Independence 判定

**Status:** Accepted  
**Date:** 2026-08-19

## Context

来源独立性直接影响“多份证据”的可信度。转载、镜像、新闻稿改写和同源 API 可能造成伪共识。

## Decision

MVP 使用启发式 dependency_group + independence_score，不追求一次完成完整来源谱系图。

信号包括 canonical URL、same publisher/domain、explicit citation、文本高相似、发布时间邻近、共同 upstream source、GitHub fork/镜像关系。先产生 pairwise dependency evidence，再聚合 dependency_group。Resolution 计算独立证据数时按 group 降权，而不是简单按 URL 数量。

## Alternatives Considered

**按域名完全去重**：会误伤同一域内真正独立文档。

**完全依赖 LLM**：成本高且不稳定。

## Consequences

能显著降低明显伪共识，同时保持实现可控。复杂跨域转载仍可能漏判，后续可增加图算法。

## Implementation Rules

independence_score 必须保存理由；不确定时宁可标记 unknown/partial，不要强行判定独立。
