# ADR-0015: Phase 0 Python 基础技术栈

**Status:** Accepted  
**Date:** 2026-08-19

## Context

Phase 0 需要 `pyproject.toml`、typed settings、SQLite migration、Repository 实现和测试。如果不冻结最小技术栈，执行 Agent 容易为了同一问题引入多套库或过早引入 Web/Agent framework。

## Decision

### Python

使用：

```text
Python >= 3.12
```

### Domain

使用标准库优先：

- `dataclasses`
- `enum`
- `datetime`
- `uuid`
- `typing`

Domain 层不依赖 ORM、Pydantic model 或厂商 SDK。

### Persistence

Phase 0 使用：

- SQLAlchemy 2.x：SQLite persistence / repository implementation；
- Alembic：显式、版本化 schema migration。

ORM model 放在 storage/infrastructure 层，与 Domain dataclass 分离。

### Configuration

使用 `pydantic-settings` 或等价的单一 typed-settings 机制读取环境变量。

不要同时混用多套配置框架。

### Tests

使用：

- pytest。

默认测试完全离线。

### Lint

允许并推荐 Ruff 作为单一快速 lint/format 工具。

Phase 0 不强制引入额外复杂 pre-commit 体系；若配置，应保持很小。

### Logging

Phase 0 使用 Python 标准 `logging`，输出结构清晰即可。不要为了 logging 引入独立平台 SDK。

## Explicitly Deferred

Phase 0 不引入：

- FastAPI；
- OpenAI SDK；
- LangChain / LlamaIndex；
- Celery；
- Redis client；
- vector database client；
- graph database client。

这些并非永久禁止，而是当前没有实现需求。

## Alternatives Considered

### 纯 sqlite3，不用 SQLAlchemy/Alembic

可以更轻，但本项目已经明确未来迁移 PostgreSQL，且 Domain 关系较多。使用 SQLAlchemy + Alembic 可以在不过度增加复杂度的前提下获得明确 schema、migration 和后续迁移空间。

### Pydantic 作为 Domain model

当前拒绝。Domain 应保持纯净，外部输入/输出验证未来可在 API/adapter 边界使用 DTO。

### 现在就加入 FastAPI

拒绝。Phase 0 没有服务端 API 验收要求。

## Consequences

`pyproject.toml` 的 Phase 0 runtime 依赖应保持极小，大致只覆盖 persistence 和 settings；测试/lint 放入 dev dependency group。

执行 Agent 不得因为创建空模块而引入对应框架。

## Implementation Rules

- Domain imports 不出现 `sqlalchemy`；
- 测试不需要真实 API key；
- migration 由 Alembic 显式管理，不依赖 ORM 启动时自动建表作为长期方案；
- 新增任何主要 runtime dependency 时在最终报告说明理由。
