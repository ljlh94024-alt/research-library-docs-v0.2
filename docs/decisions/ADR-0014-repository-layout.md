# ADR-0014: Phase 0 仓库与数据目录布局

**Status:** Accepted  
**Date:** 2026-08-19

## Context

早期文档中出现了两处可能导致实现 Agent 分叉的表达：

1. `PROJECT.md` 曾示例 `src/domain/`、`src/storage/` 等直接位于 `src/` 下，而本地开发约定使用 `src/research_library/`；
2. `PROJECT.md` 曾示例 `data/raw/`，而 Storage ADR 与本地开发文档将正式 Snapshot 放在 `data/snapshots/`。

Phase 0 必须消除这种歧义，否则不同 Agent 会生成互不兼容的目录结构。

## Decision

业务 Python package 固定为：

```text
src/research_library/
```

Phase 0 推荐仓库布局：

```text
research-library/
├── AGENTS.md
├── PROJECT.md
├── PHASE0_START_HERE.md
├── pyproject.toml
├── .env.example
├── docs/
├── src/
│   └── research_library/
│       ├── domain/
│       ├── ingestion/
│       ├── refinery/
│       ├── retrieval/
│       ├── orchestrator/
│       ├── storage/
│       ├── llm/
│       └── api/
├── tests/
├── data/
│   ├── snapshots/
│   ├── fixtures/
│   └── temp/
└── scripts/
```

正式来源内容只以 `SourceSnapshot` 语义进入：

```text
data/snapshots/<source-id>/<snapshot-id>/
```

`data/raw/` 不再使用。

`data/temp/` 仅用于可丢弃中间文件，任何最终 Evidence/Claim/KnowledgeAtom 不得只引用 temp 文件作为 provenance。

## Alternatives Considered

### 顶级 `src/domain/` 等多个包

拒绝。容易污染 import namespace，也让未来打包与发布不够清晰。

### 同时保留 `data/raw/` 与 `data/snapshots/`

当前拒绝。两者语义容易重叠。若未来确实存在“尚未被接纳为 SourceSnapshot 的下载缓存”，应通过新的 ADR 明确定义生命周期、清理策略和 provenance 边界。

## Consequences

所有 Phase 0 代码、测试和文档使用统一 import：

```python
from research_library...
```

所有正式 Snapshot filesystem 测试以 `data/snapshots/` 的结构为基准。

## Implementation Rules

- 不创建第二套正式 raw storage；
- Snapshot `content_ref` 使用相对于 Snapshot root 的相对路径；
- 测试使用临时 Snapshot root，不写入仓库正式数据目录；
- `src/research_library/` 是唯一业务 package root。
