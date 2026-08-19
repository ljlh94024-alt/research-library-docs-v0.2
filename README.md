# Research Library / 研究资料库

研究资料库是一个面向 AI 项目和 Agent 的可追溯知识底座。它将原始来源处理为 Evidence、Claim、ResolvedClaim 与 KnowledgeAtom，而不是把文档切块后直接交给 RAG。

## 为什么做

传统 RAG 擅长“找到相关文本”，但不天然解决来源重复、时间变化、证据冲突、事实归一、长期知识维护和完整溯源。本项目把这些问题放到 Knowledge Refinery 中统一处理。

## MVP

```text
Source → Snapshot → Evidence → Claim → Normalize → Link → Resolve → Confidence → KnowledgeAtom
```

## 开发原则

- 中小项目优先，先单体模块化。
- SQLite + filesystem 起步。
- LLM 输出是候选，不是事实。
- Provenance 是一级功能。
- 不追求一次解决 Truth Discovery、Knowledge Graph 和大型本体。

## 文档入口

- `PROJECT.md`：项目定位、边界和总体原则。
- `AGENTS.md`：编码 Agent 行为规范。
- `docs/architecture/`：系统设计。
- `docs/decisions/`：已接受 ADR。
- `docs/roadmap/`：MVP 顺序与非目标。
- `docs/operations/`：本地开发与运行约定。
