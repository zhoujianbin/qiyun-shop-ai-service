# Tasks

## 1. 后端

- [x] 1.1 在 `app/schemas/knowledge.py` 增加 `VersionCreateRequest`（`content_md` 必填、`change_summary` 可选）与复用 `VersionBase` 响应；验证：`python -c "from app.schemas.knowledge import VersionCreateRequest"`
- [x] 1.2 在 `app/services/knowledge_governance.py` 实现 `create_version`：校验文档存在、版本号 = max+1、`checksum=sha256(content)`、`source_kind=MANUAL`、`status=DRAFT`、复用切片器生成 PENDING 切片、写审计；验证：服务层单测覆盖版本号与切片
- [x] 1.3 在 `app/api/v1/knowledge.py` 注册 `POST /knowledge/documents/{document_pk}/versions`，权限 `knowledge:document:write`，带 `response_model`；验证：`app.openapi()` 出现该路径
- [x] 1.4 并发保存撞唯一键时返回 409 而不是 500；验证：单测模拟重复版本号
- [x] 1.5 写 `tests/test_knowledge_version_create.py`（版本号递增、切片重建、文档不存在 404、只读身份 403）；验证：`python -m pytest -q tests/test_knowledge_version_create.py`

## 2. 前端

- [x] 2.1 `web/src/api/endpoints/knowledge.ts` 增加 `createVersion`；验证：`npx tsc --noEmit`
- [x] 2.2 `EditorPage` 增加文档选择（搜索 + 载入当前版本内容）与"保存为新版本"按钮，成功后提示新版本号；验证：未选文档时按钮禁用
- [x] 2.3 保存成功后失效 `knowledge` 相关 query，使详情页版本时间线即时刷新；验证：保存后切到详情页可见新版本

## 3. 契约与验收

- [x] 3.1 重新导出契约并核对前端调用：`python scripts/export_openapi.py` + `python scripts/check_frontend_contract.py`；验证：`problems=0`
- [x] 3.2 全量回归：`python -m pytest -q` 与 `cd web && npx tsc --noEmit && npm run build`；验证：0 failed、构建成功
- [x] 3.3 更新 `docs/知识库运维.md` 的编辑章节（保存 → 提交审核 → 发布链路）；验证：文档命令/步骤可照做
