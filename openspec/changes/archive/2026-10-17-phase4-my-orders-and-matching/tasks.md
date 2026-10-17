# Tasks

## 1 新工具 query_my_orders

- [x] 1.1 `tool_registry` 新增 `query_my_orders`：入参 `{product_keyword?, status?, limit?}`（严格 Schema，`limit` 1–10 默认 5），返回单号/状态/下单时间 + 明细（商品名、数量、售后状态）；验证：单测覆盖“按商品词过滤”“按状态过滤”“limit 上限”
- [x] 1.2 客户隔离：客户只能看到本人订单（走一期 `list_orders` 的 `_apply_scope`）；验证：拿他人订单号构造用例不越权，D 组用例
- [x] 1.3 不要求订单级核验：`requires_identity=False`，可见范围仅由 `actor.customer_id` 决定；验证：未核验会话仍能列出本人订单；后续 `query_order` 仍被门禁挡住
- [x] 1.4 `llm_tools()` 清单从 9 → 10；验证：`D1` 单测计数

## 2 路由与提示词

- [x] 2.1 `classify_rule` 增加 `MY_ORDER_WORDS`（我订单/我的订单/订单里/我的单/我买的）→ 进工具分支；验证：路由单测（含“订单怎么取消”**不**进工具分支的负例）
- [x] 2.2 工具分支提示词补：“用户提到自己的订单但没给单号时先调 `query_my_orders` 列单，不要直接索要单号”；验证：真实模型走查 + 评测用例

## 3 归一模糊匹配

- [x] 3.1 `ontology.normalize_question` 增加 2-gram 兜底：唯一最优且 ≥0.5 才采纳；多候选并列放弃；验证：新增 3 条单测（错别字命中 / 并列放弃 / 无关词不命中）
- [x] 3.2 记录命中方式（`exact` / `fuzzy`）到返回结构与 `metadata.ontology`；验证：trace 可见

## 4 产品名宽松命中（仅排序）

- [x] 4.1 `normalize_question` 增加 `boost_entities`：问题含产品 `name` 的 ≥2 字子串时收录该产品实体；验证：单测“门锁”命中产品但不产生 `product_scope`
- [x] 4.2 `rank_by_ontology` 合并 boost 实体；验证：同一查询加/不加 boost，命中集合相同、顺序不同

## 5 启动预热

- [x] 5.1 `app/main.py` lifespan 起后台线程预热 embedding（`APP_ENV=test` 跳过）；验证：重启后首个问题耗时对比（记录前后数字）
- [x] 5.2 预热失败只告警不阻塞；验证：模拟异常时服务仍可启动

## 6 评测与收口

- [x] 6.1 新增 3 条 L1 用例（2 条必须调 `query_my_orders`，1 条不得调）；验证：`H1/H3`
- [x] 6.2 全量回归 + 契约 + 前端构建；验证：`A1`–`A3`
- [x] 6.3 更新 `docs/四期/01`（工具清单 9 → 10）、`docs/四期/04` 手工测试指南（新增一条“我订单里门锁那个”）；验证：文档与代码一致
