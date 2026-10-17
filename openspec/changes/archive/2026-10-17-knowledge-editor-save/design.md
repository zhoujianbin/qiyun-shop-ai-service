# Design

## Context

二期已交付：导入（`knowledge_import`）、切片器（`knowledge_chunk.split_markdown`）、版本状态机与发布（`knowledge_governance`）、审计与 outbox。缺的只是"以文本新建版本"这一个入口。见 `proposal.md`。

## Goals / Non-Goals

**Goals**

- 一个端点完成"文本 → 新草稿版本 → 重新切片 → 审计"，不引入新的数据模型。
- 与导入产生的版本在语义上完全一致（`source_kind` 不同、其余同构），使后续提交审核/发布门禁无需特判。

**Non-Goals**

- 不做版本内容的行级 diff 或在线协同。
- 不做"保存即发布"。
- 不改前端编辑器已有切片预览逻辑。

## Decisions

### 决策 1：新增端点而不是复用导入

`POST /knowledge/documents/{document_pk}/versions`，请求体 `{content_md, change_summary?}`。

- **备选**：把文本包成单文件再走 `/import/jobs` —— 需要伪造 multipart 与 front matter，且会新建一个导入任务，语义错位。
- **代价**：与导入共享切片逻辑，必须保证 `checksum` 计算口径一致（同样对 content 取 sha256）。

### 决策 2：新版本一律 DRAFT

不提供"直接生效"，生效仍走 提交审核 → 发布（含门禁）。这样发布门禁是唯一入口，不会出现绕过门禁写入 ACTIVE 的路径。

**备选**：允许管理员直接发布 —— 会绕过"变更摘要必填 + 阻断冲突检查"，否决。

### 决策 3：`source_kind` 记为 `MANUAL`

与导入的 `MD_BUNDLE` 区分，便于治理报告与审计追溯"这条内容是导入来的还是后台手写的"。该值已在 CHECK 约束内，无需改 DDL。

### 决策 4：切片与向量

复用 `split_markdown(content_md)`，切片 `embedding_status=PENDING`、`identity_level` 继承文档；向量化交给 worker（与导入一致，不在请求内计算）。

### 决策 5：幂等

请求是 JSON，一期中间件按 `method+path+body` 指纹处理 `Idempotency-Key`，语义正确（同一 key + 同一内容 → 回放同一响应），**不需要**加入豁免名单。

## Risks / Trade-offs

| 风险 | 缓解 |
|---|---|
| 同一文档并发保存产生相同版本号 | 依赖 `UNIQUE(document_pk, version)`，冲突时返回 409 由前端重试 |
| 保存后忘记提交审核，版本长期停留 DRAFT | 详情页版本时间线标注状态；概览待审数只统计有审核任务的 |
| 切片器未来调整导致新旧版本切片口径不同 | 已发布版本不重建切片；重算靠 `reindex_embeddings.py` |

## Migration Plan

无数据迁移。发布新 restful 端点后重新导出契约即可。

## Open Questions

无。
