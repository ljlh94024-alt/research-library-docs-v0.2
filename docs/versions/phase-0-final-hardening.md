# Phase 0 Final Hardening 版本说明

**版本：** `phase-0-final-hardening`
**基线：** `0001_phase0`
**迁移头：** `0002_phase0_hardening`
**日期：** 2026-08-19

## 本版本内容

- 冻结 `0001_phase0` 为历史显式 DDL，并以新 migration 增加完整性约束；
- 为处理产物补充 StageRun 外键、索引和 processing provenance 查询；
- 将置信度/独立性评分改为浮点字段并加入 `[0, 1]` 检查约束；
- 为核心事实实体加入 append-only、精确重放幂等和同 ID 冲突保护；
- 让 Snapshot 在数据库落库失败时清理本次新写入的文件；
- 增加迁移回放、约束、文件一致性、不可变性、溯源和 CI 验收覆盖。

## 版本规则

- 不修改已发布 migration；schema 变化递增创建新的 Alembic revision。
- 不覆盖已发布 ADR、冻结规范或版本说明；新边界建立新文档并更新根目录索引。
- 新版本必须注明基线、迁移头、行为变化、验收命令和是否仍处于 Phase 0。
- 未经新的 ADR 明确批准，不进入 Phase 1 的 ingestion、真实 LLM、服务端 API、
  向量检索或智能 orchestrator。
