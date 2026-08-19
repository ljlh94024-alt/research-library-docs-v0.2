# ADR-0016: Phase 0 持久化完整性与版本演进

**Status:** Accepted
**Date:** 2026-08-19

## Context

Phase 0 的第一版基础已经发布到 `0001_phase0`。后续修复必须能从空库、旧库和
多次重复运行中得到同一份可验证结果。直接修改历史 migration、用可变 upsert
覆盖事实记录，或把处理来源只留在 JSON 中，都会破坏可回放性和审计能力。

## Decision

1. 在本 PR 内，`0001_phase0` 根据基线 `01e0ce8` 实际运行时创建的 schema
   做一次性显式冻结，包含六个历史的、无 FK 的 processing provenance 列。
   本 PR 新增 `0002_phase0_hardening` 承载 FK、约束和新增列。PR 合并后，
   `0001_phase0` 永不再修改；之后每个 schema 变化都建立新的有序 revision。
2. 文档同样按版本新增。历史 ADR、冻结文件和验收文件保持原样；新的边界或
   修订写入新的 ADR/版本说明，并在 `DOCUMENTS.md` 建立索引。
3. SourceSnapshot、Evidence、Claim、ClaimGroup、EvidenceLink、ResolvedClaim
   和 KnowledgeAtom 使用按 ID 的 append-only 语义：完全相同的重放幂等，字段
   不同的同 ID 写入失败。Source、Contradiction、PipelineRun 和 StageRun 保持
   可更新状态。
4. 所有处理产物的 `created_by_stage_run_id` 使用可空外键；完整 processing
   provenance 查询遇到缺失引用必须失败，而不是静默返回不完整链路。
5. 置信度和独立性评分统一使用 `Float`，数据库以 `NULL` 或 `[0, 1]` 检查约束
   拒绝越界值。

## Consequences

- 新版本可以验证 fresh upgrade、legacy upgrade 和 downgrade/upgrade round-trip。
- 运行历史与知识事实不会被普通重跑覆盖。
- 新增 schema 或实现规则时，必须新增 migration/ADR/测试，并更新文档索引。
- Phase 0 仍保持 SQLite + filesystem、标准库 Domain 和离线测试边界；本 ADR
  不引入 Phase 1 能力。
