# Retrieval 与 Serving 架构

## 1. 目标

查询优先命中结构化 KnowledgeAtom，而不是每次从原始 chunk 重新推理。Evidence 与 Snapshot 用于解释、校验和补充上下文。

## 2. 查询顺序

```text
Query
→ query parse
→ structured filters
→ full-text retrieval
→ optional vector recall
→ rank KnowledgeAtom
→ attach provenance summary
→ optionally expand Evidence/Snapshot
```

## 3. 返回对象

默认返回 statement、subject/predicate/object、confidence、status、validity、source summary、evidence refs。上层请求 `include_evidence=true` 时再返回原始证据片段。

## 4. 冲突查询

如果最相关 ClaimGroup 处于 conflicting 或 unresolved，Retrieval 不应伪装为单一确定答案。应返回主要候选、冲突来源和当前 confidence。

## 5. 召回策略

MVP 优先 SQL 条件 + FTS。Embedding 只在自然语言语义召回需要时引入，且不改变 KnowledgeAtom 作为主服务对象的原则。

## 6. API 分层

公开 API 不暴露数据库内部表结构。使用稳定 DTO，并允许后续存储迁移而不破坏客户端。
