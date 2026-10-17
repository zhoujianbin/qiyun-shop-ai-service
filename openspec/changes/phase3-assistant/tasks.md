# Tasks

> 五组：数据与地基 → 会话与流式 → RAG 编排 → 身份核验与转人工 → 前端与集成。
> 每组自带测试与文档；每条任务的"验证"必须当场可执行。

## 1. 数据与地基

- [x] 1.1 在 `db/schema.sql` 增 `CREATE SCHEMA assistant` 与 **6 张表**（conversation / message / **citation** / handoff / identity_verification / retrieval_trace），含唯一键、部分唯一索引与 CHECK；验证：空库建表后表数 55 → **61**
- [x] 1.2 写 `db/migrations/0007_assistant_schema.sql`（幂等）；验证：对一期+二期库执行 `apply_migrations.py` 后表数 **61**，再执行一次全部 skipped
- [x] 1.3 重跑 `scripts/gen_models.py`；验证：`AssistantConversation` 等 **6 个**模型存在，`git diff --exit-code` 在无手改时为空
- [x] 1.4 追加 `ai:chat:read`、`ai:chat:write`、`ai:handoff:read`、`ai:handoff:write`、`ai:trace:read` 五个权限码与 `AI_AGENT`/`AI_SUPERVISOR` 授权（含迁移）；验证：`select count(*) from shared.app_permission where module='ai'` 返回 5
- [x] 1.5 在 `app/core/config.py` 增 `llm_provider`、`llm_base_url`、`llm_model`、`llm_api_key`、`llm_timeout_seconds`、`assistant_context_rounds`、`assistant_message_max_chars`、`assistant_rate_limit`；验证：`APP_ENV=test` 时 provider 解析为 fake
- [x] 1.6 实现 `app/integrations/llm.py`：`stream_chat()` 支持 OpenAI 兼容流与 fake；**只转发 `delta.content`，丢弃 `reasoning_content`**；验证：fake 返回确定性文本，单测不联网；接真模型时断言流里不出现推理内容
- [x] 1.7 为 schema 与权限写测试；验证：`python -m pytest -q tests/test_assistant_schema.py`

## 2. 会话与流式

- [x] 2.1 实现 `assistant_conversation.py`：建会话、追加消息（seq 单调）、关闭会话、上下文窗口取数；验证：关闭后追加返回 409
- [x] 2.2 实现会话可见性（本人 / 有 `ai:chat:read` 的员工 / 被指派人），越权 404；验证：客户 A 访问客户 B 会话返回 404
- [x] 2.3 实现 SSE 端点 `POST /api/v1/ai/conversations/{id}/messages:stream`：meta → ping(15s) → delta → citations → done/error，响应头含 `Cache-Control: no-cache` 与 `X-Accel-Buffering: no`；**先落 USER + 占位 ASSISTANT(STREAMING)，流结束更新终态**；验证：httpx 读流断言事件顺序与响应头
- [x] 2.4 把 SSE 路径加入中间件幂等豁免；验证：不携带 `Idempotency-Key` 也能建立流
- [x] 2.5 实现限流与长度上限（429 / 422）；验证：超限用例有明确错误码
- [x] 2.6 写清理任务 `scripts/assistant_cleanup.py`：按保留期删已关闭会话（6 张表级联），并把超 2 分钟仍 `STREAMING` 的消息置 `FAILED`；验证：造过期会话与僵尸消息各一，执行后 6 张表无残留、消息变 FAILED
- [x] 2.7 为会话与流式写测试；验证：`python -m pytest -q tests/test_assistant_conversation.py`

## 3. RAG 编排与护栏

- [x] 3.1 实现 `assistant_graph.py`（plan → execute ⇄ replan → finalize，一条件边）：计划 ≤2 步、最大 4 步、最多 1 次 replan、总超时 30s；计划用 Pydantic 校验，非法退化为固定两步；`ToolSpec` 带 `read_only/requires_identity/scope`；验证：单测直接调用节点，超限场景各一条
- [x] 3.2 实现意图识别节点（知识问答/实时事实/身份核验请求/人工请求），**规则词表优先、未命中才调 LLM planner**；验证：四类样例各命中预期分支，且规则命中时 LLM 调用次数为 0
- [x] 3.3 检索节点调用二期 `knowledge_retrieval.search`，不重复实现检索；验证：单测 monkeypatch 搜索返回，断言命中被带入状态
- [x] 3.4 实现"无命中不调模型"：首次无命中返回**澄清反问**，同一问题再空则固定拒答；验证：单测断言两种情形 fake LLM 均未被调用
- [x] 3.5 实现生成节点（流式）与服务端引用装配（只从 `hits` 生成）；验证：回答的 citations 每项都能回指真实切片
- [x] 3.6 实现实时事实边界：订单/物流/库存类问题不给具体值，只给口径与引导；验证：问物流位置时回答不含轨迹
- [x] 3.7 实现高风险护栏：读 `knowledge.rule` 中 `source_kind='escalation'` 的 `triggers` 词表做关键词匹配，命中即取该规则 `forbid` 追加安全提示；验证：远程开锁问题不含操作步骤，且 trace 记录命中的 rule_id
- [x] 3.8 实现问答链路留痕 `retrieval_trace` 与按消息反查接口；验证：一次问答后能按 message_id 查到记录
- [x] 3.9 实现模型超时/异常降级（错误事件 + 消息 FAILED）；验证：注入超时后消息状态为失败
- [x] 3.10 为 RAG 链路写测试（图节点、引用、拒答、护栏、留痕、降级）；验证：`python -m pytest -q tests/test_assistant_answer.py`

## 4. 身份核验与转人工

- [x] 4.1 实现 `assistant_handoff.py::verify_identity`：订单号 + 收货手机后四位比对，写 `identity_verification` 与过期时间；验证：正确/错误用例各一
- [x] 4.2 实现会话级可见范围放宽（只读、30 分钟过期失效）+ **固定事实快照** `order_fact_snapshot`（订单号/状态/实付/下单时间/物流状态+运单号/售后进度，6 字段白名单）；验证：过期后按未核验处理；快照响应正则断言不含完整手机/地址/卡号
- [x] 4.3 实现失败计数与连续 3 次强制转人工；验证：第 3 次失败后核验被拒且生成 handoff
- [x] 4.4 实现统一失败话术（不可枚举）；验证：两种失败返回同一文案，且不含个人信息
- [x] 4.5 实现转人工 5 触发（`USER_REQUEST`/`HIGH_RISK_RULE`/`IDENTITY_FAILED`/`NO_HIT`/`MODEL_ERROR`）+ **认领制**状态机：认领置 `conversation.ai_paused=true`（AI 停止自动回答），关单必填 `summary` 并恢复 `ai_paused=false`；**不自动建售后工单**；验证：五类原因各一条，认领后提问不再触发模型，缺结论关单 422
- [x] 4.6 接审计与 outbox 事件（`ai.handoff.created` 等）；验证：`shared.outbox_event` 出现对应事件
- [x] 4.7 为核验与转人工写测试；验证：`python -m pytest -q tests/test_assistant_handoff.py`

## 5. 前端与集成

- [ ] 5.1 新增 `web/src/api/endpoints/assistant.ts`（含 SSE 读取封装）与 `web/src/types/assistant.ts`；验证：`npx tsc --noEmit`
- [ ] 5.2 客户侧独立页 `/assistant` + `CustomerShell` 入口按钮：气泡/头像/时间分组、思考态→流式、输入区、拒答与失败提示；游客可问知识类，问订单类引导登录+核验；验证：入口按钮可跳转；游客问订单被引导，且不产生订单信息
- [ ] 5.3 客服工作台会话列表（最近时间/消息数/转人工状态）；验证：按权限过滤
- [ ] 5.4 引用侧栏（文档标识/版本/标题路径/行号）：**客服端可跳转二期文档详情，客户侧只展示不跳转**；验证：客户侧引用卡无链接，客服端点击跳转成功
- [ ] 5.5 转人工处理（接单/关闭需结论/权限可见性）；验证：无权限看不到按钮，缺结论提交被拒
- [ ] 5.6 路由与菜单纯追加 + 构建门禁；验证：`npx tsc --noEmit && npm run build` 通过，首屏 gzip < 260KB，助手页面独立分包
- [ ] 5.7 写 `docs/三期对话协议.md`（SSE 事件、错误码、引用结构）与运维章节；验证：文档中的事件序列与实测一致

## 6. 契约与验收

- [ ] 6.1 重新导出契约并核对前端调用；验证：`check_frontend_contract.py` problems=0
- [ ] 6.2 全量回归：`python -m pytest -q` 与前端构建；验证：0 failed、构建成功、一期 53 项仍在
- [ ] 6.3 端到端演练：登录 → 建会话 → 提问（知识类）→ 流式回答带引用 → 问物流 → 拒答 → 核验失败 3 次 → 转人工 → 工作台接单关闭；验证：一条脚本跑完并输出证据
- [ ] 6.4 写三期总结（做了什么/没做什么/已知限制/下一步）；验证：已知限制可逐条对应 design 的 Risks
