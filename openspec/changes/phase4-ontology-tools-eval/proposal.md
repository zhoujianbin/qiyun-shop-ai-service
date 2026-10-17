# Proposal

## Why

三期把"答得有据"做完了，但只能答**知识类**问题：用户说"我的订单到哪了"，系统要么给固定口径、要么转人工——因为三期没有任何一条通往一期业务数据的路径。同时知识切片与商品/部件/故障/政策之间的关系完全没有建模，检索只能靠语义相似度，无法按实体收窄；而一期 `ToolSpec` 与 `citation.entity_tags` 三个预埋点，实测**一个都没通电**（`input_schema` 从未被消费、`active_verification()` 全库无调用点、`entity_tags` 由正则冒充）。

四期是规划最后一期，要把"能答"变成"能查、能办、可度量"。但"能办"意味着模型可以触发真实改单——没有确认与幂等，任何一次幻觉都会变成真实的订单状态变更。所以四期真正的难度不在加功能，而在**给写操作建立可审计、可回滚的边界**，并让"没变差"可被机器验证。

## What Changes

- **本体**：新建 `ontology` schema（entity / relation / alias / entity_tag / chunk_entity，含 `DRAFT/APPROVED` 审核态），从 `knowledge_raw/13_结构化规则/` 导入，目标 67 实体 / ≥100 关系 / 7 类谓词
- **本体↔检索**：编排新增 `normalize` 节点（**检索前**实体归一，直接映射到二期已支持的 `filters.product_scope`），检索后做**深度 1** 扩展；深度 2 递归 CTE 仅用于回答取证。**二期 `knowledge_retrieval.py` 零改动**
- **工具**：9 个工具（7 只读 + 2 写），严格 JSON Schema（`additionalProperties:false`）+ `description` 强制写"何时不要用"；工具定义 = **代码单真源**，不建注册表（避免二期 `product_catalog` 式双真源）
- **写安全**：`assistant.pending_action`（`PROPOSED → CONFIRMED → EXECUTED`）+ 二次确认 + CAS 幂等 + 3 时点审计 + 频次闸 + **单轮仅 1 个写工具**（一期服务自带 commit，多写不可回滚）
- **BREAKING（行为）**：`identity_level` 改由服务端从 `active_verification()` 推导，**忽略客户端入参**（修复三期既存缺陷 F21：任意登录用户传 `"agent"` 即可读内部文档）。字段名/类型不变，但依赖客户端自报的调用方会看到可见范围收窄
- **流式**：`llm.py` 累积 `delta.tool_calls`（`id`/`name` 只在首块、`arguments` 逐 token 拼接、`finish_reason=tool_calls` 收口），`stream()` 改为产出结构化事件；采用**单段流式 + 首轮叙述缓冲**（实测流式决策 690–915ms vs 非流式 1115–1160ms）
- **SSE**：新增 `tool` 与 `action` 两个事件；老三期 6 个事件的载荷**一字不改**
- **评测**：`eval/cases/*.yaml` 60 条 + 三层分工（L1 fake 100% 阻断 / L2 真模型记录 / L3 人工抽检）；runner 用 pytest，零新工具
- **迁移**：`0009`–`0011` 三个文件，表数 **61 → 68**；新增 7 个权限码（4 个 `tool:*` + 3 个 `ontology:*`）

## Capabilities

### New Capabilities

- `ontology`: 本体建模（实体/关系/别名/标签/切片映射）、审核态、从结构化规则导入、递归 CTE 遍历，以及与二期检索的集成边界（只使用二期已支持的 filter 键）
- `tool-calling`: 工具注册与协议（JSON Schema、描述规范、参数校验）、9 个工具清单、只读与写操作分级、待确认动作与二次确认、幂等与审计、身份核验门禁、失败与降级话术、流式事件扩展
- `assistant-eval`: 评测用例形态与来源、三层分工、pytest runner、零退化门禁、报告产出与不入库约束

### Modified Capabilities

- `assistant-answer`: 新增 `normalize` 前置节点与检索后扩展；`identity_level` 改由服务端推导；新增 `tool`/`action` 流式事件与"叙述不早于事实"约束；补充 `finish_reason=length` 判失败与业务拒绝透传的降级口径

## Impact

| 类型 | 内容 |
|---|---|
| 新增表 | `ontology` 5 张；`assistant.pending_action`、`assistant.tool_call`（61 → 68） |
| 新增接口 | `/api/v1/ai/actions/*`（confirm/cancel/get/list）、`/api/v1/knowledge/ontology/*`（import/entities/relations/aliases/review/graph/relink） |
| 修改文件 | `app/integrations/llm.py`（tools 透传 + tool_calls 解析 + fake 脚本化）、`app/services/assistant_graph.py`（normalize/tool_loop 节点）、`app/api/v1/assistant.py`（流式分发 + identity_level 推导 + action 接口）、`app/services/knowledge_retrieval.py` **不动** |
| 新增文件 | `app/services/ontology.py`、`app/services/tool_registry.py`、`app/services/action.py`、`eval/`、`tests/test_eval_*.py` |
| 前端 | `web/src/types/assistant.ts` 的 `StreamEvent` 6 → 8；新增确认卡片与事实卡片；知识后台加本体页 |
| 契约 | `openapi.json`/`openapi.yaml` 重导出并通过 `check_frontend_contract.py` |
| 权限 | 7 个新权限码；`AI_AGENT` 加 `tool:read`，`AI_SUPERVISOR` 加 2 个 `tool:write:*`，`KNOWLEDGE_ADMIN`/`REVIEWER`/`EDITOR` 加 `ontology:*` |
| 不变量 | 一/二/三期表结构、接口路径与字段、前端既有类型、既有权限码**全部不变**；`handoff.reason` 的 CHECK 枚举不动（工具失败沿用 `MODEL_ERROR` + `summary`） |
