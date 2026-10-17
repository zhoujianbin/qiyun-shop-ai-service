# Proposal — 编辑器保存（手动新建版本）

## Why

二期归档后，后台编辑器只能**预览切片**，不能保存：`POST /knowledge/documents/{id}/versions` 在接口清单里，但没有任何任务覆盖，导致"在后台改一段话"的唯一路径是重新走导入。运营改错别字、补一句话都要准备文件并重传，改稿闭环断在最后一步。

## What Changes

- 新增 `POST /knowledge/documents/{document_pk}/versions`：以 `content_md` 新建一个 **DRAFT** 版本（版本号 = 当前最大值 +1），重新切片并置 `PENDING`，写审计。
- 编辑器页新增"选择文档 + 载入当前版本 + 保存为新版本"：保存成功后展示新版本号，并提示"提交审核后才可发布"。
- 不改数据模型、不改一期任何文件；不涉及发布/审核逻辑。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

（无既有 requirement 被改写。新增两条 requirement：）

- `knowledge-governance`: 新增「手动新建版本」——后台可直接以文本新建草稿版本
- `knowledge-admin-ui`: 新增「编辑器保存新版本」——编辑器可保存并展示新版本号

## Impact

**后端**
- 修改：`app/api/v1/knowledge.py`（1 个端点）、`app/services/knowledge_governance.py`（`create_version`）、`app/schemas/knowledge.py`（请求/响应模型）
- 复用：`knowledge_import` 的切片器；`audit.record`
- 契约：`openapi.json`/`openapi.yaml` 需重新导出，前端契约脚本必须 problems=0

**前端**
- 修改：`web/src/pages/knowledge/EditorPage.tsx`（加文档选择与保存）、`web/src/api/endpoints/knowledge.ts`（1 个方法）
- 无新增依赖

**测试**
- 新增 `tests/test_knowledge_version_create.py`（版本号递增、切片重建、404、权限）
