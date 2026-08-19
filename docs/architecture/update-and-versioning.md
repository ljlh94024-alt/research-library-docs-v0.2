# 更新、时间与版本管理

## 1. Snapshot 驱动更新

来源变化由新 Snapshot 表示。相同 content_hash 可跳过重复 Refinery；内容变化则触发 change detection 与受影响知识重算。

## 2. 知识状态

KnowledgeAtom 至少支持 active、superseded、historical、invalid、conflicting。不要用物理删除表示“旧了”。

## 3. 时间范围

Claim 与 ResolvedClaim 可以带 valid_from、valid_until、observed_at 和 temporal qualifiers。系统必须区分“2023 年使用 MySQL”和“2026 年使用 PostgreSQL”，避免把演化误判为矛盾。

## 4. Pipeline Version

每次运行记录 pipeline_version。任一会影响结果的算法、Prompt 或解析规则变化必须能通过版本号追踪。

## 5. 重算策略

MVP 使用显式命令或任务触发重算，不实现复杂增量依赖图。优先保证正确和可审计，后续再优化只重算受影响节点。
