# Tasks

> 分组按可独立验收的边界切；依赖顺序即编号顺序。每组末尾的"验证"是硬判据，对应 `docs/四期/02_验收清单.md` 的编号。

## 1 数据与迁移

- [x] 1.1 `db/migrations/0009_ontology_schema.sql`：新建 `ontology` schema 与 entity / relation / alias / entity_tag / chunk_entity 五表，含唯一键、CHECK 枚举、索引、表注释；全部 `CREATE ... IF NOT EXISTS`；验证：空库重放两次表数稳定，`B1`
- [x] 1.2 `db/migrations/0010_assistant_action.sql`：`assistant.pending_action`（含 `UNIQUE(conversation_id, action_key)` 与 `UNIQUE(conversation_id, message_id)`）、`assistant.tool_call`；验证：并发插同 key 冲突，`B4`、`B5`
- [x] 1.3 `db/migrations/0011_ontology_tool_permissions.sql`：7 个权限码（`tool:read`/`tool:write:order`/`tool:write:aftersales`/`tool:admin`/`ontology:read`/`ontology:write`/`ontology:review`）+ 角色绑定，`ON CONFLICT DO NOTHING`，空库跳过；验证：`B6`，且 `AI_AGENT` 仅有 `tool:read`
- [x] 1.4 更新 `db/schema.sql` 与 `scripts/gen_models.py` 产出；验证：`B3` = 68，`git diff` 只增不删，`B7`

## 2 本体服务与导入

- [x] 2.1 `app/services/ontology.py`：实体/关系/别名 CRUD + 审核态流转（`DRAFT→APPROVED→DEPRECATED`）；验证：只有 APPROVED 参与检索，spec 场景"未审核实体不参与检索"
- [x] 2.2 导入器：解析 `13_结构化规则/` 的 `product_catalog`、`product_warranty`、`escalation_matrix`、`policy_rules`，映射为实体与 7 类谓词，幂等；验证：`C1`（83 实体 / 65 关系，其中 59 生效）、`C2`（连续两次 `symptom_new=0`/`relation_new=0`）
- [x] 2.3 别名最长匹配器：`alias` 表 + 最长优先 + 上位词不误判；验证：`C5`
- [x] 2.4 递归 CTE 遍历（`depth` 列 + 路径数组防环），两种用途（1 跳检索 / 2 跳取证）；验证：`C3`、`C4`
- [x] 2.5 `chunk_entity` 回填与 `relink`（逻辑键 `document_id+version+chunk_ord`）；验证：`C7`（换版重挂且抽取调用次数为 0）；实测 452 条映射覆盖 81/158 篇，二次执行 inserted=0
- [x] 2.6 后台接口：`/knowledge/ontology/{import,entities,relations,aliases,review,graph,chunks/relink}`，带 `response_model`、`ontology:*` 权限、写接口 `Idempotency-Key`；验证：契约检查通过

## 3 本体↔检索集成

- [x] 3.1 `assistant_graph.py` 新增 `normalize` 节点：问题 → 实体 → `{product_scope, entity_ids}`；验证：`C5` 场景 + `search()` 收到的 filters 断言
- [x] 3.2 检索调用**只传** `category`/`product_scope`；零实体命中时 filters 为空；验证：`git diff app/services/knowledge_retrieval.py` 为空（`C6` 一票否决）
- [x] 3.3 检索后一跳扩展：邻接实体最多再检索 1 次，hits 合并去重后重编 `rank`，步数仍受 `MAX_STEPS=4`；验证：`C3` 与既有闸门用例全绿
- [x] 3.4 `citation.entity_tags` 改由本体回填（移除正则抽取），`citation` 表结构不动；验证：标签值 ∈ `ontology.entity.code`

## 4 工具协议（`llm.py` 改造）

- [x] 4.1 `_payload()` 支持 `tools`/`tool_choice` 透传；验证：对真模型调用返回 `finish_reason=tool_calls`
- [x] 4.2 `complete()` 解析 `message.tool_calls`（`arguments` 为字符串 → `json.loads`）；验证：非法 JSON 走失败分支不抛异常，`D4`
- [x] 4.3 `stream()` 改为产出结构化事件：累积 `delta.tool_calls`（`id`/`name` 取首块、`arguments` 逐片拼接、`finish_reason` 收口），丢弃 `reasoning_content`；验证：`G2`（tool_calls 不出流）
- [x] 4.4 `FakeProvider` 增脚本化模式：按用例 `must_call_tool` 产出对应 `tool_calls`；验证：`H7`
- [x] 4.5 决策轮 `max_tokens` 单配 ≥600；`finish_reason=length` 判失败；验证：`G4`
- [x] 4.6 改造 `assistant.py` 的流式分发（`yield from` → for 循环分发）；验证：老三期 6 事件载荷字段集合不变（`G1`）

## 5 工具注册表与只读工具

- [x] 5.1 `app/services/tool_registry.py`：9 个工具定义（沿用 `ToolSpec`），补 `requires_confirm`，每个 `description` 含"何时不要用"，写工具含"只生成待确认动作"；验证：`D1`、`D2`
- [x] 5.2 参数校验层：`additionalProperties:false` + 必填 + 类型；校验失败不调一期函数；验证：`D3`
- [x] 5.3 `resolve_order(db, actor, order_no)`（新薄封装，带 `customer_id` 过滤，**不改一期函数**）；验证：`D6`
- [x] 5.4 六个只读工具接一期服务（`catalog.search_products`/`order.get_order`/`fulfillment.list_shipments`/`payment.list_payments`/`aftersales.list_applications`/`invoice.list_invoices`）；验证：`D5`
- [x] 5.5 工具调度节点 `tool_loop`：最多 3 次；只读失败按 §5.7 分级；每次调用写 `tool_call`（args 脱敏）；验证：`D7`、`G5`、`G6`

## 6 写操作与确认

- [x] 6.1 `app/services/action.py`：propose（生成 `PROPOSED` + `action_key=sha256(tool+归一化参数)`）、confirm（CAS）、cancel、过期判定；验证：`E1`、`E2`、`E3`、`E6`
- [x] 6.2 两个写工具接 `order.cancel` / `aftersales.create`；确认卡片摘要复用 `order_fact_snapshot` 6 字段白名单；验证：`E7`（无 PII）
- [x] 6.3 频次闸：单会话写 ≤3、同一 order 24h 取消 ≤1；单轮仅 1 写；验证：`E8`、`D7`
- [x] 6.4 三时点审计 + 四类 outbox 事件；验证：`E4`、`E5`
- [x] 6.5 接口 `POST /ai/actions/{id}/confirm`、`/cancel`、`GET /ai/actions/{id}`、`GET /ai/conversations/{id}/actions`；写接口带 `Idempotency-Key`；验证：重复 confirm 幂等（`E3`）
- [x] 6.6 写失败不自动重试 + "未做任何改动"话术；验证：`E9`

## 7 核验门禁与 F21

- [x] 7.1 工具节点前置检查 `active_verification(conversation_id)` + `order_no` 精确匹配；验证：`F1`、`F2`、`F3`
- [x] 7.2 写工具在 confirm 时再校验 `expires_at`；验证：`F3` + 过期写拒绝
- [x] 7.3 **F21 修复**：`identity_level` 由服务端推导（VERIFIED→customer / 员工权限→agent / 否则 public），忽略客户端入参；验证：`F4`（一票否决）、`F5`
- [x] 7.4 3 次失败锁 → `IDENTITY_FAILED` 转人工沿用；验证：`F6`

## 8 流式事件与前端

- [x] 8.1 新增 `tool` 事件（`{name,status,latency_ms}`）与 `action` 事件（`{id,tool,summary,impact,irreversible,expires_at}`）；验证：`G1`、`G3`
- [x] 8.2 B2 叙述缓冲：带 `tools` 轮次的 `content` 先缓冲，按 `finish_reason` 分支下发；验证：`G3`
- [x] 8.3 `web/src/types/assistant.ts` 的 `StreamEvent` 6 → 8；确认卡片 + 事实卡片组件；验证：`A2`、`A3`
- [x] 8.4 知识后台新增本体页（列表 + 审核 + 图谱深度 2 查看）；验证：`A3`
- [x] 8.5 重导出 `openapi.json`/`openapi.yaml`；验证：`A2`

## 9 评测闭环

- [x] 9.1 `eval/cases/*.yaml` 60 条（knowledge 20 / tool_read 15 / tool_write 10 / identity 5 / refuse+safety 10），从 20 篇 SCN + 9 篇 SOP 转化，含 SCN-017/018 红队；验证：`H1`、`H2`
- [x] 9.2 `tests/test_eval_contract.py`：字段齐、id 唯一、`category` 合法、`layer` 合法；验证：`H1`
- [x] 9.3 `tests/test_eval_l1.py`：fake 脚本化执行链路断言；验证：`H3`
- [x] 9.4 `tests/test_eval_l2.py` + `pytest.ini` 加 `eval_live` marker 与 `addopts`；验证：`A7`
- [x] 9.5 `make eval` / `make eval-report` → `var/eval_report.{json,md}`，L1/L2 分表无总分；验证：`H4`、`H6`
- [x] 9.6 门禁自检：人为改坏一条用例必须让 `make test` 失败；验证：`H5`

## 10 收口

- [x] 10.1 全量回归 + 契约 + 前端构建；验证：`A1`–`A4`
- [x] 10.2 更正三期文档三处不一致（LangGraph 措辞、`entity_tags` 正则、`input_schema` 未消费）；验证：文档与代码一致
- [x] 10.3 更新 `docs/知识库运维.md` 的本体维护章节与 `docs/四期/` 定稿；验证：— 
