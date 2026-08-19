# 数据与 Provenance 流

## 1. 两类 Provenance

系统区分 Domain Provenance 与 Processing Provenance。

```text
Domain: KnowledgeAtom → ResolvedClaim → Claim → Evidence → Snapshot → Source
Processing: Object → StageRun → PipelineRun → model/prompt/version
```

## 2. Domain Provenance

Domain Provenance 解释“这条知识基于什么证据”。Claim 与 Evidence 通过 EvidenceLink 表示 supports、contradicts、qualifies、mentions。ResolvedClaim 聚合一个 ClaimGroup 下的候选事实，KnowledgeAtom 只发布当前可服务的结论。

## 3. Processing Provenance

每次完整处理创建 PipelineRun；每个阶段创建 StageRun。StageRun 记录 stage_name、stage_version、model_provider、model、prompt_id、prompt_version、input_refs、output_refs、状态、时间与错误。

## 4. Append-Oriented

Provenance 默认追加，不覆盖。重新处理同一 Snapshot 会产生新的 StageRun 和对象版本。系统可以标记新的对象为 current，但历史仍可审计。

## 5. No-Orphan Rule

Evidence、Claim、ResolvedClaim、KnowledgeAtom 均不得成为无法追溯生成来源的孤儿对象。Provenance 断裂的对象默认不可发布。

## 6. 典型查询

- “这条 KnowledgeAtom 来自哪些来源？”
- “某个 Snapshot 生成了哪些 Claims？”
- “某个模型/Prompt 版本生成了哪些对象？”
- “为什么这条 Claim 被判为 conflicting？”
- “新 Snapshot 到来后哪些 Atom 被 superseded？”
