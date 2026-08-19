# Phase 0 架构冻结

**Status:** Frozen for Phase 0  
**Date:** 2026-08-19

## 1. 目的

本文件把已经分散在 PROJECT、架构文档和 ADR 中、但会直接影响第一版代码形态的约束收束到一处。

它不是长期不可变的“终极架构”。它只意味着：**Phase 0 实现过程中，开发 Agent 不应自行重新设计这些部分。**

若确有必要改变，先提出 ADR。

## 2. 冻结边界

### 2.1 进程与部署

Phase 0 是单进程、模块化单体、本地优先。

没有：

- 微服务；
- 外部任务队列；
- 分布式锁；
- 独立缓存层；
- 多租户。

### 2.2 Python package

正式业务包固定：

```text
src/research_library/
```

`src/` 只是 source root，不直接包含 `domain/`、`storage/` 等顶级业务包。

### 2.3 Domain 与 Infrastructure 分离

Domain 层只表达领域事实、状态和规则。

```text
Domain
  ↑
Application / Pipeline
  ↑
Storage / LLM / Ingestion adapters
```

Domain 不得反向导入 Infrastructure。

SQLAlchemy models 不是 Domain models。

### 2.4 正式数据目录

正式 Snapshot：

```text
data/snapshots/<source-id>/<snapshot-id>/
```

测试/演示 fixture：

```text
data/fixtures/
```

可随时删除的处理中间文件：

```text
data/temp/
```

不使用 `data/raw/` 作为独立正式层。

理由：SourceSnapshot 已经承担“被系统冻结的原始来源状态”这一语义。增加 raw 层会形成两个事实来源并导致 provenance 歧义。

### 2.5 Snapshot 不可变

已创建 Snapshot 的以下内容不可原地修改：

- `source_id`
- `retrieved_at`
- `content_hash`
- 原始内容
- 正式 `content_ref`

来源变化时创建新的 `SourceSnapshot`。

规范化文本、解析缓存等派生物如果需要更新，应作为可重建派生物或新版本，不得改写原始 Snapshot 的事实语义。

### 2.6 ID

核心持久化对象使用应用生成的稳定字符串 ID。

Phase 0 建议 UUID4 的字符串表现；不得依赖 SQLite 自增 ID 作为跨层或未来迁移后的公共标识。

### 2.7 时间

内部时间统一使用带时区的 UTC datetime。

序列化输出采用 ISO 8601。

不要在 Domain 中保存模糊的本地无时区时间。

### 2.8 JSON 字段

JSON 只用于：

- metadata；
- qualifiers；
- provider/raw extension；
- 暂无必要结构化的扩展信息。

核心关系必须用显式字段/关系表表达，不能把 provenance 和主要状态塞进任意 JSON。

## 3. Phase 0 最小领域链

核心链固定为：

```text
Source
  ↓
SourceSnapshot
  ↓
Evidence
  ↕ EvidenceLink
Claim
  ↓ ClaimGroup membership
ClaimGroup
  ↓
ResolvedClaim
  ↓
KnowledgeAtom
```

以及：

```text
Claim ↔ Claim
   Contradiction
```

`KnowledgeAtom` 不得直接把 Source URL 当作唯一 provenance。

## 4. Pipeline 冻结

Phase 0 不实现完整 Refinery，只建立运行骨架。

完整阶段顺序仍以 PROJECT/Knowledge Refinery 为准：

```text
Evidence Extraction
→ Claim Extraction
→ Claim Normalization
→ Evidence Linking
→ Source Independence
→ Contradiction Detection
→ Claim Resolution
→ Confidence
→ KnowledgeAtom Build
```

Phase 0 的 `PipelineRunner` 不需要实现这些算法，只需要让未来这些 stage 能按稳定接口接入，并让 `PipelineRun`/`StageRun` 可持久化。

## 5. Provenance 冻结

最小发布知识必须有：

```text
KnowledgeAtom
→ ResolvedClaim
→ at least one Claim
→ at least one Evidence
→ SourceSnapshot
→ Source
```

Processing provenance 还应能追踪关键对象的 `created_by_stage_run_id` 或等价引用。

Phase 0 不要求把所有 provenance 抽象成通用图数据库。

## 6. Storage 冻结

Phase 0：

```text
SQLite + Local Filesystem
```

关系数据进 SQLite；大体积 Snapshot 内容进 filesystem。

未来 PostgreSQL/S3/pgvector 是迁移方向，不是 Phase 0 兼容性测试目标。

Repository contract 要避免 SQLite 特有细节泄漏到 Domain/Application。

## 7. LLM 冻结

Phase 0 只允许：

```text
LLMClient interface
FakeLLMClient
```

真实 provider 属于后续阶段。

Refinery/Application 只能依赖内部接口，不能直接 import OpenAI 或其他厂商 SDK。

## 8. API 冻结

ADR-0010 定义的是未来外部契约方向。

Phase 0 不要求启动 REST server。

若需要 DTO，可定义纯类型；不要因为未来 API 提前引入 FastAPI。

## 9. Orchestrator 冻结

Phase 0 不实现智能研究循环。

最多保留清晰接口或轻量 runner 边界；不要建立自循环、多 Agent 通信协议或复杂状态机。

## 10. 测试冻结

默认测试必须：

- 离线；
- 不要求 API key；
- 不要求公网；
- 不污染仓库正式 `data/snapshots/`；
- 使用临时 SQLite 和临时目录；
- 可重复执行。

## 11. 什么情况下必须新 ADR

实现若需要改变以下任一项，先停止并提出 ADR：

- Domain 核心对象或关系；
- Snapshot 的不可变语义；
- `data/snapshots/` 正式路径；
- SQLite + filesystem 基础方案；
- Provenance 最小链；
- 包结构；
- Phase 0 基础技术栈；
- 引入外部队列/服务/数据库。
