# Knowledge Refinery 架构

## 1. 定义

Knowledge Refinery 是 Research Library 的核心，负责把未经验证的 SourceSnapshot 转换成可长期使用的 KnowledgeAtom。中间不允许从 Snapshot 直接跳到最终知识。

## 2. 总流水线

```text
SourceSnapshot
→ Evidence Candidate
→ Claim Extraction
→ Claim Normalization
→ Evidence Linking
→ Source Independence
→ Contradiction Detection
→ Claim Resolution
→ Confidence
→ Knowledge Atom
```

## 3. SourceSnapshot

冻结来源在某个时间点的状态。来源发生变化时创建新 Snapshot，不修改旧 Snapshot。每个 Snapshot 至少保存 source_id、retrieved_at、content_hash、content_ref 和 metadata。

## 4. Evidence Candidate

Evidence Candidate 是可能用于证明、否定或限定某个事实的来源片段。必须保留原文、上下文、来源位置、Snapshot ID 和抽取方式。本阶段不判断真假。

## 5. Claim Extraction

从 Evidence 中抽取独立事实陈述。一个段落可拆成多个 Claim。Claim 要尽可能原子化，但不要为了“原子”丢失限定词与时间条件。

## 6. Claim Normalization

不同表达需要统一成可比较形式。第一版优先 canonical statement + entity identifiers + predicate + value + qualifiers，不建立大型 Ontology。

## 7. Evidence Linking

Claim 与 Evidence 是多对多关系。关系至少支持 supports、contradicts、qualifies、mentions。`mentions` 不得当作 `supports`。

## 8. Source Independence

利用 domain、canonical URL、引用链接、文本相似度、发布时间和 metadata 聚合 dependency_group。第一版目标只是避免明显重复计数，不追求完美的来源谱系推断。

## 9. Contradiction Detection

对 same subject + same predicate + incompatible value 建立冲突候选，同时考虑 temporal scope、context 和 qualifiers，避免把历史变化误判为逻辑矛盾。

## 10. Claim Resolution

Resolution 综合证据直接程度、来源质量、独立性、时间、上下文、支持/反对证据，并允许 resolved、unresolved、conflicting、insufficient_evidence、historical_change 等结果。Resolution 不等于“让 LLM 选一个”。

## 11. Confidence

Confidence 拆分 source_quality、evidence_directness、independence、agreement、freshness、extraction_confidence 等分量，并保留理由。数字只是汇总，不替代解释。

## 12. Knowledge Atom

KnowledgeAtom 是对外发布的最小知识单元，保存 subject、predicate、object、statement、confidence、status、validity 与 provenance refs。

## 13. 为什么不直接 RAG

传统 Document → Chunk → Embedding → Top-K → LLM 仍可用于 Evidence discovery，但不是长期知识模型。Research Library 的主链是 Documents → Evidence → Claims → Resolution → Knowledge Atoms → Retrieval。

## 14. MVP 算法标准

Evidence 可先用段落切分 + LLM 判断；Claim Extraction 用 structured output；Normalization 用实体归一 + canonical statement + 相似度；Independence 用域名/引用/文本相似；Contradiction 用结构候选 + LLM verify；Resolution 用规则分数 + LLM explanation。重点是接口和数据结构正确。

## 15. 可重放性

同一个 Snapshot 必须能够用新的 pipeline_version、prompt_version 和 model 重新处理。旧运行保留，active/current 状态由系统选择，不无痕覆盖。

## 16. Human Override

允许人工 reject evidence、merge/split claims、override resolution、lock atom，但人工操作也必须记录 provenance。
