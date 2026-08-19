# ADR-0002: 第一阶段存储方案

**Status:** Accepted  
**Date:** 2026-08-19

## Context

系统同时需要保存结构化领域对象、大体积原始 Snapshot、Provenance、历史版本以及未来可选的 embedding。当前属于中小规模早期项目，不应一开始部署多个基础设施。

## Decision

开发初期采用 SQLite + Local Filesystem；稳定后迁移目标为 PostgreSQL + Filesystem/S3-compatible Object Storage + optional pgvector。

SQLite 保存领域对象、关系、PipelineRun、StageRun、版本与索引。大型原始内容保存到 `data/snapshots/<source-id>/<snapshot-id>/`，数据库仅保存 content_ref。每个 Snapshot 计算 SHA-256。业务层通过 Repository 接口访问存储，不直接绑定 SQLite。开发 ORM 可使用 SQLAlchemy，但 Domain Object 不与 ORM Model 强绑定。

## Alternatives Considered

**PostgreSQL from Day One**：部署复杂度高，MVP 数据量不需要。

**Neo4j**：当前 provenance 可由关系数据库表达。

**独立 Vector DB**：embedding 不是事实主存储。

## Consequences

单机开发简单、可离线测试、依赖少，同时保留未来迁移空间。迁移触发条件包括并发写、SQLite 锁竞争、服务端部署、多用户或成熟的 pgvector 需求。

## Implementation Rules

Snapshot 文件路径使用相对路径；数据库和 snapshots 目录必须一起备份；不要把大型原始文件直接塞进核心关系表。
