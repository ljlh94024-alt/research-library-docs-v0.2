# Phase 0：Codex 开工入口

> 当前阶段：**工程骨架 / Architecture Skeleton**  
> 状态：**Ready for implementation**  
> 原则：先把边界、数据链路和测试站稳，再进入真正的 Knowledge Refinery 算法实现。

## 1. 你现在要做什么

你是本仓库 Phase 0 的执行开发 Agent。

本轮目标不是实现产品功能，而是建立一个可运行、可测试、后续不需要推倒重来的最小工程骨架。

开始改动前，按顺序阅读：

1. `AGENTS.md`
2. `PROJECT.md`
3. `docs/architecture/phase-0-freeze.md`
4. `docs/decisions/ADR-0001-domain-model.md`
5. `docs/decisions/ADR-0002-storage.md`
6. `docs/decisions/ADR-0004-provenance.md`
7. `docs/decisions/ADR-0005-pipeline-execution.md`
8. `docs/decisions/ADR-0007-database-schema.md`
9. `docs/decisions/ADR-0011-testing-strategy.md`
10. `docs/decisions/ADR-0014-repository-layout.md`
11. `docs/decisions/ADR-0015-python-foundation.md`
12. `docs/roadmap/phase-0-acceptance.md`

若实现发现这些文件之间存在冲突，停止扩大改动，按 `AGENTS.md` 的权威优先级处理，并在报告中列出冲突。

## 2. 本轮必须创建的工程骨架

目标目录：

```text
research-library/
├── pyproject.toml
├── .env.example
├── src/
│   └── research_library/
│       ├── __init__.py
│       ├── config.py
│       ├── domain/
│       ├── ingestion/
│       ├── refinery/
│       ├── storage/
│       ├── llm/
│       ├── retrieval/
│       ├── orchestrator/
│       └── api/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── data/
│   ├── snapshots/
│   ├── fixtures/
│   └── temp/
└── scripts/
```

其中只有 Phase 0 需要的模块必须有实际实现；后续阶段模块允许只有接口、类型或最小占位，但不要创建空洞的大量 boilerplate。

## 3. Phase 0 必须实现

### 3.1 Domain

至少包含：

- `Source`
- `SourceSnapshot`
- `Evidence`
- `Claim`
- `ClaimGroup`
- `EvidenceLink`
- `Contradiction`
- `ResolvedClaim`
- `KnowledgeAtom`
- `PipelineRun`
- `StageRun`

以及必要的状态 Enum、关系类型和稳定 ID 类型。

Domain 层不得依赖 SQLAlchemy、Alembic、HTTP 框架、OpenAI SDK 或其他 provider SDK。

### 3.2 Storage

至少包含：

- Repository Protocol/ABC；
- SQLite 最小实现；
- 版本化 migration；
- Snapshot filesystem；
- SHA-256 content hash；
- 相对 `content_ref`；
- 临时测试数据库与临时 snapshot root 支持。

### 3.3 Provenance

必须真实跑通：

```text
KnowledgeAtom
→ ResolvedClaim
→ Claim
→ Evidence
→ SourceSnapshot
→ Source
```

不要只在类型定义里“看起来存在”；至少一个集成测试要保存并从 Repository 重新加载这条链。

### 3.4 LLM abstraction

只实现：

- `LLMClient` 接口；
- `LLMRequest` / `LLMResponse`；
- `FakeLLMClient`。

Fake 必须确定、离线、可配置 fixture response。

**不要**接真实 provider。

### 3.5 Pipeline skeleton

只实现最小的：

```text
PipelineRun
  └── StageRun
```

能够：

- 创建运行；
- 记录阶段开始/成功/失败；
- 保存版本信息；
- 保留历史；
- 用 Fake stage 做一次最小重跑测试。

不要实现完整 Refinery 算法。

## 4. 本轮明确禁止

不要实现：

- 真实 HTTP/网页抓取；
- GitHub adapter；
- OpenAI 或其他真实 LLM API；
- Embedding provider；
- Vector DB / pgvector；
- FastAPI/完整 REST 服务；
- UI；
- Agent loop；
- Kafka、Redis、RabbitMQ、Celery；
- Docker/Kubernetes；
- Neo4j/Elasticsearch；
- LangChain/LlamaIndex 等 Agent/RAG framework。

如果某项测试不依赖这些东西就能完成，不要引入它们。

## 5. 实施顺序

严格优先：

```text
Python package / config
→ Domain
→ Repository contracts
→ SQLite migrations
→ Snapshot filesystem
→ Provenance integration
→ FakeLLMClient
→ PipelineRun / StageRun
→ tests
```

不要先写 API 和 Orchestrator。

## 6. 完成后必须运行

至少执行：

```bash
pytest
```

若项目配置了 Ruff，再执行：

```bash
ruff check .
```

不要把真实网络/API 作为默认测试前置条件。

## 7. 最终报告格式

完成后只需要报告：

1. 实际创建/修改的文件树；
2. 已实现 Domain 对象；
3. Repository 与 migration 状态；
4. Provenance 测试结果；
5. FakeLLM/Pipeline 测试结果；
6. `pytest`/lint 结果；
7. 与架构文档存在的任何偏差；
8. Phase 1 前仍缺什么。

不要在完成 Phase 0 后自行进入 Phase 1。
