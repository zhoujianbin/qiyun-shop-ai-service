# 二期需求探索笔记（决策台账）

> 性质：**探索笔记，不是 OpenSpec 产物**。本文件不建 change、不产生 spec、不驱动实现。
> 用途：把二期探索第 1 轮（B1 边界 / B2 页面与审核 / B3 检索形态 / 取舍 a·c / 数据接口 / 验收草案）的结论固定下来，供后续 `/openspec-propose` 直接引用。
> 范围：二期（企业知识库平台）。三/四期只记录"预埋点"，不记录设计。
> 上游材料：`docs/二期/01_二期需求说明书.md`、`docs/二期/02_验收清单.md`、`docs/schema.sql`、`docs/栖云智家_第一期详细设计.md`、`knowledge_raw/`。

---

## 0 事实基线（这一轮实测出来的，优先于文档表述）

| # | 事实 | 证据 | 与文档的出入 |
|---|---|---|---|
| F1 | 一期 `knowledge.chunk.embedding` 是 `vector(1024)`，已建 HNSW | `docs/schema.sql`（knowledge 段） | 与 bge-small-zh-v1.5 的 512 维冲突，§4.3 已提出改法 |
| F2 | `knowledge_raw/` 共 **169 个文件 = 158 md + 10 yaml + 1 py** | `find knowledge_raw -type f` | §2 与验收 C1 说"169 篇 Markdown"，口径错误 |
| F3 | 一期权限表叫 **`shared.app_permission`**，不是 `shared.permission` | `docs/schema.sql`、`docs/seed_all.sql` | §3、验收 B4 的 SQL 需改 |
| F4 | 一期 API 路径**无 `/admin` 前缀**，89 条全扁平 `/api/v1/<resource>` | `openapi.json` | 二期 `/knowledge/*` 与一期风格一致，无需另设前缀 |
| F5 | 一期**没有** `db/migrations/`；`db/schema.sql` 是唯一 DDL 真源，`app/models/generated.py` 由 `scripts/gen_models.py` 自动生成（文件头注明"请勿手工修改"） | `db/`、`scripts/gen_models.py` | §4.4 要引入第二套迁移机制，需定义"三一致" |
| F6 | `app/integrations/storage.py` 的 `ALLOWED` **不含 `.md` / `.yaml`** | 该文件 `ALLOWED` 常量 | §8「按一期附件校验」与「导入 md」直接矛盾：md 会被 `validate()` 拒 |
| F7 | 一期依赖无任何 embedding 栈（无 torch / sentence-transformers / numpy） | `requirements.txt`、venv 40 个包 | 需新增 4 个依赖，torch CPU wheel 200MB+ |
| F8 | HF 缓存 7.5GB 但**没有** `BAAI/bge-small-zh-v1.5` | `~/.cache/huggingface/hub` | 首次必须联网下载约 95MB |
| F9 | 语料体量：158 篇 md 共 **644KB**，均 4KB，`##` 标题 285 个 → 全库切片预计 **400–600 条** | `du`/`grep -c '^## '` | §8「10 万切片 P95<1.5s」与实际差两个数量级 |
| F10 | 一期 7 个角色：SUPER_ADMIN / ECOMMERCE_OPS / INVENTORY_MANAGER / AFTER_SALES / FINANCE_VIEWER / CS_SUPERVISOR / AUDITOR | `docs/seed_all.sql` | §3 的 5 个角色里只有 CS_SUPERVISOR 已存在；4 个是新增 |
| F11 | `AUDITOR` 授权语句是 `code LIKE '%:read'`，`SUPER_ADMIN` 是权限全量 | `docs/seed_all.sql` | 二期 `knowledge:*:read` 落库后重跑 seed，AUDITOR 会自动获得全库读权限 |
| F12 | 前端无任何 Markdown 渲染/编辑器依赖；路由已 `lazyEl` + `RequirePermission` | `web/package.json`、`web/src/app/routes.admin.tsx` | 新页面天然懒加载，J6/首屏预算不会被 7 个页面打破 |
| F13 | 契约检查脚本只比对**路径+方法**，不校验字段 | `scripts/check_frontend_contract.py` | A2 `problems=0` 不能证明字段对齐 |
| F14 | 一期数据隔离是**后端从 token 推导**（`_channel_scope` + `deps.check_channel_scope`），不信任前端传参 | `app/services/identity.py`、`app/api/deps.py` | 检索隔离必须沿用同一套 |
| F15 | 库内已有 `knowledge_raw/99_校验与维护/validate_knowledge.py`（front matter 必填、rule_id 引用、危险话术红线） | 该脚本 | 导入前置校验可复用之，不必重写 |
| F16 | **`docs/seed_all.sql` 不是执行路径**，只是文档快照；真实种子在 `scripts/bootstrap.py`，`AUDITOR` 的 `READ_ONLY` 在 `bootstrap.py:225` 展开成"所有 `:read` 权限" | `Makefile`、`scripts/seed.py`、`scripts/bootstrap.py` | "重跑 seed 会让 AUDITOR 获得 knowledge 读权限"的问题仍在，但**改的位置是 bootstrap.py** |
| F17 | **前端角色码与后端角色码零重叠**：后端 7 个（SUPER_ADMIN 等），前端 `ROLE_CODES` 6 个（ENTERPRISE_ADMIN 等），且前端无 AUDITOR；`permissionStore.has()` 里 `roles.includes('ENTERPRISE_ADMIN')` 分支**永不命中**。`PERMISSIONS` 常量与后端权限码另有至少 6 处不一致 | `web/src/types/permissions.ts`、`web/src/stores/permissionStore.ts`、`scripts/bootstrap.py` | 二期新增 4 个 KNOWLEDGE_* 角色与 12 个权限码时，必须先定跟哪套命名（见 D22） |

---

## 1 决策台账（已确认，按确认顺序）

### 1.1 主题 B1：知识库边界

| ID | 决策 | 内容 | 理由 | 连带 |
|---|---|---|---|---|
| D1 | **Q1=C 分形态纳管** | 10 个 yaml 中只把 **政策数值型(policy_rules, 9 条) + 保修型(product_warranty, 7 条) + 升级矩阵型(escalation_matrix, 8 条) = 24 条** 映射进 `knowledge.rule`；状态机型(order_workflow/ticket_workflow)、意图型(intent_taxonomy)、权限型(role_permissions)、目录档案型(company_profile/product_catalog/service_sla) 共 7 个文件**不入库**，仅纳入引用校验 | 5 种异构结构硬塞进一张 `condition/action/forbid` 表会把状态机写成伪条件；`intent_taxonomy.tools` 已是四期工具名，入库等于提前暴露；`role_permissions` 是业务角色，与 `shared.app_role_permission` 是两套 | §4.2 需加 `source_kind`；新增 `POST /knowledge/rules/import` 通道 |
| D2 | **Q2=A 一叶子规则一行** | `RETURN-NO-REASON-7D` 一行、`WARRANTY-QL-L3P-MAIN-24M` 一行 → 24 行 | 冲突检测需在"动作互斥"粒度判定；逐条可设 priority/生效期 | `knowledge.rule` 不做版本化（版本化留四期） |
| D3 | **Q3=A 原生 rule_id 优先** | `rule_id` 直接存 `RETURN-NO-REASON-7D` 等原生 id；§4.2 的 `KB-RULE-0001` 格式降级为"手工新建规则的默认格式" | 48 篇 md 已按原生 id 引用（实测 26 处 `rule_id` 提及、48 个文件引用规则 id），强制重编号会断链 | design 需写明两类 id 并存 |
| D4 | **Q4=C 删除验收 C1** | "169 篇批量导入成功"删除，不写替代的数量断言 | 169 是错误口径 | **残留缺口**：见 §6 风险 R3 |
| D5 | **Q5=A 商品目录以一期为真源** | `product_catalog.yaml` 不入库；`commerce.product.model_code` 为真源；不一致项进治理报告 | 消除双真源（yaml 的 `QL-L3P` 与 seed 里 `model_code` 重复） | §5.8 治理报告增第 5 类 |
| D24 | **condition 固定 6 键** | `condition` 只允许 `product_line` / `issue_type` / `order_state` / `identity_level` / `time_window` / `component`；值可为标量或标量数组（数组 = 任一命中）。`amount_threshold` 暂留 `action`，出现第 2 条运费规则时提升为第 7 键 | 5 键不够：保修类同产品不同部件（QL-L3P 2 条、QR-R5M 2 条）若 `component` 不在条件里，冲突检测会误报 BLOCK，发布门禁第一天就死锁 | 映射表见 §8；design 需加一条 lint（condition 键 ⊆ 6 键） |

### 1.2 主题 B2：后台管理页面与审核组织形态

| ID | 决策 | 内容 | 理由 | 连带 |
|---|---|---|---|---|
| D6 | **7 页全做** | overview / documents / documents/:id / editor / review / retrieval-test / governance，保持 §7 原文 | 对齐老板"后段管理页面"；新页面懒加载，不动首屏预算 | 需改 `web/src/constants/routes.ts`、`web/src/types/permissions.ts`、`web/src/layouts/AdminShell.tsx` 的 MENU（**只加条目**，见风险 R1） |
| D7 | **允许自审 + 标记** | 允许同一人审核自己提交的版本，`review_task.self_review=true` 并在发布弹窗/审计显式标注；配置 `knowledge.allow_self_review`，二期默认 true | 单人开发若强制"编辑≠审核"，每条验收都要两账号 | 验收新增 G6；`review_task` 增列 |
| D8 | **AUDITOR 显式收回** | 二期 migration 收回 AUDITOR 的 `knowledge:%` 读授权（不改表结构，只删角色-权限绑定），并同步修 `scripts/bootstrap.py:225` 的 READ_ONLY 展开条件，防止重跑 seed 回潮 | 审计员不应自动获得全库知识读权限（F11/F16） | 验收新增 B7；落地文件是 **`scripts/bootstrap.py`，不是 `docs/seed_all.sql`**（F16 更正） |
| D9 | **编辑器只引入 react-markdown** | `Input.TextArea` 编辑 + `react-markdown` 只读预览；实时切片走服务端 `POST /knowledge/preview-chunks` | 契合"不许另起炉灶"；引入编辑器框架（`@uiw/react-md-editor`）性质不同 | 二期第一个新增前端依赖，需在 design 记账（+约 15KB，进懒加载 chunk） |

### 1.3 主题 B3：检索能力对外形态

| ID | 决策 | 内容 | 理由 | 连带 |
|---|---|---|---|---|
| D10 | **单接口双段** | 只保留 `POST /knowledge/retrieval/test`，返回 `{hits:[...], debug:{vector_score,text_score,fused_score,latency_ms}}`；`hits` 为稳定引用契约，`debug` 标注"仅调试、三期勿依赖" | 三期同仓库同进程，service 层 import 即够；不开 `/retrieval/search` | 验收 L1 需改措辞；`RetrievalHit` schema 定型 |
| D11 | **identity_level 真预埋** | `document`/`chunk` 各加 `identity_level`（public/customer/agent，默认 public）；导入一律填 public；**用测试构造的 agent 级 chunk 证伪过滤** | 全 public 时过滤逻辑无法被证伪，L6 会变成纸面通过；按目录推断等于编业务规则 | 验收新增 H9；L6 措辞改 |
| D12 | **规则不参与检索** | 检索 `hits[]` 只含 chunk；规则走 `GET /knowledge/rules` 结构化查询 | `SOURCE_OF_TRUTH.md` 第 2 条：规则优先于文档且"不得自行选择更有利或更严格的一条"；向量近似召回规则方向相反；二期无意图识别，query→condition 键无法映射 | 验收新增 E7 |
| D13 | **隔离后端强制注入** | 从 token 推导可见渠道，与请求 `channel_scope` 取**交集**；前端传的超集静默收窄；越权 404 | 沿用一期 `_channel_scope` + `check_channel_scope`（F14），验收 K1 天然成立 | 检索参数校验逻辑置于 deps |

### 1.4 关键取舍 (a) 向量化 / (c) 导入格式

| ID | 决策 | 内容 | 理由 | 连带 |
|---|---|---|---|---|
| D14 | **worker + `--once`** | `scripts/knowledge_worker.py` 常驻（`FOR UPDATE SKIP LOCKED`）+ 支持 `--once` 跑一轮退出 | 验收 D4/F5/F6 变成"跑一条命令"；生产再挂常驻 | 验收新增 F8 |
| D15 | **模型自动下载 + 路径兜底** | 默认 `HF_HOME=var/models` 自动下载；配置 `EMBEDDING_MODEL_PATH` 指定时离线直用；进程内单例懒加载 | 开发开箱即用、生产可离线 | 依赖新增 4 个；首次 95MB 下载 |
| D16 | **测试用 fake embedder** | 多数测试用确定性 fake（同文本→同向量、512 维、归一化）；仅 1 条真模型 smoke 标 `@pytest.mark.slow` | 否则测试套件从 20 秒变 5 分钟 | **需注册 pytest marker**（当前无 pytest.ini/pyproject 配置，见 R4） |
| D17 | **入库不加指令前缀、查询加** | chunk 的 embedding 不带前缀；查询侧加「为这个句子生成表示以用于检索相关文章：」 | bge 系列既定用法 | 写进适配器注释 |
| D18 | **格式 MD/TXT/DOCX + yaml 规则通道** | `.md` `.txt` 走文档导入；`.yaml` 只走 `rules/import`；DOCX 用 `python-docx` | 对齐 §5.1；PDF/XLSX/CSV/HTML 后置 | **库内 0 个真实 docx**，C3 的"损坏 docx"只能靠 fixture |
| D19 | **一次请求多文件 multipart** | `POST /import/jobs` 收 `List[UploadFile]`；158 个 md 共约 644KB | 零解压风险；C1/C2 就是"一个 curl" | 不做 zip、不做目录扫描 |
| D20 | **扩一期 ALLOWED 加 `.md`/`.yaml`** | `app/integrations/storage.py` 的 `ALLOWED` 加两行 | 满足 §8「按一期附件校验」字面；副作用是一期附件接口也能传 md（无害） | 已纳入 D21 白名单，边界见下 |

### 1.5 边界与迁移记录（R1/R5 收口）

| ID | 决策 | 内容 | 理由 | 连带 |
|---|---|---|---|---|
| D21 | **白名单 + 纯追加**（实施后更正为 9 个文件，见 design.md 决策 1） | 二期只允许动 6 个一期文件，且每个文件 `git diff` **只有 `+` 行、没有 `-` 行**（新增条目/新增字典键，不改已有行）。6 个文件：`app/api/v1/router.py`、`web/src/constants/routes.ts`、`web/src/types/permissions.ts`、`web/src/layouts/AdminShell.tsx`、`app/integrations/storage.py`、`scripts/bootstrap.py` | 可用一条命令机器校验：`git diff -U0 -- <file> \| grep -E '^-[^-]'` 必须为空。零触碰要么改一期架构（+2 人日 + 回归风险），要么躲不掉 `include_router` 一行；宽口径则失去可审计性 | design 需产出「一期兼容性声明」表；验收新增 A7 |
| D22 | **角色命名后端为准，前端只追加** | 新增 4 个角色码按后端 bootstrap 风格：`KNOWLEDGE_ADMIN` / `KNOWLEDGE_REVIEWER` / `KNOWLEDGE_EDITOR` / `CS_AGENT`；前端 `ROLE_CODES` 只**追加**这 4 个，**不修**一期 6 vs 7 的不一致 | 二期自身自洽，且不动一期已有行（满足 D21）；借机修齐要改 6 删 7 加 + 改 ROLE_LABELS + 修 `has()`，属改已有行 | 一期"角色码对不上"作为**已知遗留**写进 N8 二期总结 |
| D23 | **新增 `shared.schema_migration`** | 第 7 张新表（shared schema）：`version`、`file_name`、`checksum`、`applied_at`、`applied_by`、`duration_ms`、`success` | 语义干净、`checksum` 可抓"迁移文件被改过"；复用 `shared.audit_log` 会污染 `shared:audit:read` 的语义与查询；文件记录在多环境/-reset 后易误判 | 表数 48→**55**；A5 命令行数字改 55 |

---

## 2 数据草案

### 2.1 一期已有 3 张表的改动（9 加列 + 1 改列 + 1 重建索引 + 0 改约束）

| 表 | 改动 | 备注 |
|---|---|---|
| `knowledge.chunk` | `embedding` 1024→**512**；重建 HNSW | `docs/schema.sql` 与 `db/schema.sql` 双写 |
| `knowledge.chunk` | **加** `embedding_status`（PENDING/READY/FAILED，默认 PENDING） | §5.5 要求它，但 §4.2 的 6 张新表里没有——文档漏项 |
| `knowledge.chunk` | **加** `identity_level`（默认 public） | D11 |
| `knowledge.document` | **加** `identity_level`、`effective_date` | `region`/`tags` 可放 `metadata jsonb`，本期不加列 |
| `knowledge.document_version` | **加** `change_summary`、`published_at`、`published_by`、`source_kind` | `change_summary` 是 §5.3 发布弹窗的落点 |
| `knowledge.document` | `status` CHECK **不改** | SCHEDULED 只在 `document_version.status` 表达（该表已有此枚举）；`document.status` 保持"有生效版本"语义 |

### 2.2 二期新增 7 张表（knowledge 6 张 + shared 1 张）

| 表 | 关键字段 | 用途 |
|---|---|---|
| `knowledge.rule` | `rule_id`(原生 id, 唯一)、`source_kind`(policy/warranty/escalation/manual)、`condition jsonb`、`action jsonb`、`forbid jsonb`、`priority`、`status`、`effective_from/until`、`conflict_group`、`source_file`、`source_line`、`tenant_id`、`created_by/at` | 24 条 yaml 规则 + 手工规则 |
| `knowledge.rule_conflict` | `rule_a`、`rule_b`、`conflict_type`、`severity`(BLOCK/WARN)、`status`(OPEN/RESOLVED)、`detected_at`、`resolved_by/at` | E3/E4 |
| `knowledge.review_task` | `document_version_id`、`assignee_id`、`status`、`due_at`、`decision`、`decided_at`、`note`、**`self_review`** | D7 |
| `knowledge.review_comment` | `version_id`、`author_id`、`anchor jsonb`(title_path/chunk_ord/char_range)、`content`、`resolved`、`parent_id` | 批注；`parent_id` 留作回复（UI 可延后） |
| `knowledge.import_job` | `source_type`(MD_BUNDLE/RULE_YAML)、`file_name`、`checksum`、`status`、`total`、`succeeded`、`failed`、`skipped`、`errors jsonb`、`idempotency_key`、`created_by` | `skipped` 是 C2 的证据；`total/succeeded` 是 C1 删除后**唯一**能证明导入成功的地方 |
| `knowledge.retrieval_log` | `query`、`filters jsonb`、`top_k`、`hits jsonb`、`latency_ms`、`actor_id`、`identity_level`、`hit_count`、`kind`(test/prod) | H7；`kind` 为三期留 |
| `shared.schema_migration` | `version`、`file_name`、`checksum`、`applied_at`、`applied_by`、`duration_ms`、`success` | D23：迁移执行记录；`checksum` 能抓"迁移文件被改过" |

**knowledge schema 保持 6 张**：不做 `import_job_item`——169 个文件的错误清单塞 `errors jsonb` 够用，多一张表多一套模型一致性测试。第 7 张是 `shared.schema_migration`（D23）。

**表数变化**：一期 48（shared 13 + commerce 32 + knowledge 3）→ 二期 **55**（shared 14 + commerce 32 + knowledge 9）。A5 的命令行数字随之改为 55。

---

## 3 接口草案（26 条路径 / 32 个操作；★ = 草案新增，§6 原清单没有）

| # | 方法 | 路径 | 权限 |
|---|---|---|---|
| 1 | GET | `/knowledge/documents` | document:read |
| 2 | POST | `/knowledge/documents` | document:write |
| 3 | GET | `/knowledge/documents/{id}` | document:read |
| 4 | PATCH | `/knowledge/documents/{id}` | document:write |
| 5 | POST | `/knowledge/documents/{id}/archive` | document:archive |
| 6 | GET | `/knowledge/documents/{id}/versions` | document:read |
| 7 | POST | `/knowledge/documents/{id}/versions` | document:write |
| 8 | GET | `/knowledge/versions/{id}` | document:read |
| 9 | POST | `/knowledge/versions/{id}/submit` | document:write |
| 10 | POST | `/knowledge/versions/{id}/publish` | document:publish |
| 11 | POST | `/knowledge/versions/{id}/rollback` | document:rollback |
| 12 | GET | `/knowledge/versions/{id}/chunks` | document:read |
| 13 ★ | POST | `/knowledge/preview-chunks` | document:write |
| 14 | GET | `/knowledge/review/tasks` | review:read |
| 15 ★ | GET | `/knowledge/review/tasks/{id}` | review:read |
| 16 | POST | `/knowledge/review/tasks/{id}/claim` | review:write |
| 17 | POST | `/knowledge/review/tasks/{id}/decide` | review:write |
| 18 | GET | `/knowledge/review/tasks/{id}/comments` | review:read |
| 19 | POST | `/knowledge/review/tasks/{id}/comments` | review:write |
| 20 | GET | `/knowledge/rules` | rule:read |
| 21 | POST | `/knowledge/rules` | rule:write |
| 22 ★ | GET | `/knowledge/rules/{id}` | rule:read |
| 23 | PATCH | `/knowledge/rules/{id}` | rule:write |
| 24 | POST | `/knowledge/rules/check-conflicts` | rule:read |
| 25 ★ | GET | `/knowledge/rule-conflicts` | rule:read |
| 26 ★ | PATCH | `/knowledge/rule-conflicts/{id}` | rule:write |
| 27 ★ | POST | `/knowledge/rules/import` | document:import |
| 28 | POST | `/knowledge/import/jobs` | document:import |
| 29 | GET | `/knowledge/import/jobs/{id}` | document:import |
| 30 | POST | `/knowledge/retrieval/test` | retrieval:test |
| 31 | GET | `/knowledge/governance/report` | governance:read |
| 32 | GET | `/knowledge/overview` | document:read |

**6 个 ★ 的理由**（原文自相矛盾，不是加料）：13 补 §7 实时切片预览无接口；22 有 PATCH 无 GET；25/26 补 E4「标记 RESOLVED」无接口、治理页无法下钻冲突；15 补批注锚定需详情；27 是 D1 分形态纳管的落地入口。

**12 个权限码**（登记到 `shared.app_permission`，`module='knowledge'`）：document:read/write/import/archive/publish/rollback、rule:read/write、review:read/write、retrieval:test、governance:read。

---

## 4 预埋落位（§L1–L8）

| # | 预埋点 | 落在哪 | 本期状态 |
|---|---|---|---|
| L1 | 检索可服务化 | `app/services/knowledge_retrieval.py::search(query, filters, top_k)` 纯函数 | 实现；**不预置 HTTP 服务身份** |
| L2 | 引用结构化 | `RetrievalHit`：document_id/version/title_path/line_start/line_end/chunk_ord/snippet | 实现 |
| L3 | 规则键语义化 | `rule.condition` 固定键：product_line/issue_type/order_state/identity_level/time_window | 实现 |
| L4 | 事件出口 | `shared.outbox_event`：knowledge.version.published/archived/rolled_back/chunk.embedded | 实现 |
| L5 | 权限可扩展 | 12 个 knowledge:* 三段式；ai:*/tool:* 只写文档 | 实现 |
| L6 | 身份等级过滤 | `identity_level` 列 + 检索参数 + 构造数据证伪 | 实现 |
| L7 | schema 规划 | design 写明 `assistant` schema 存 conversation/message，本期不建 | 只写文档 |
| L8 | 无提前实现 | `git grep -iE 'langgraph\|conversation\|tool_call\|ontology' -- app/` 无命中 | 验收命令 |

---

## 5 验收草案变更索引（原 81 条 → 94 条）

| 动作 | 条数 | 编号 |
|---|---|---|
| 删除 | 1 | C1 |
| 修改 | 14 | A5、B3、B4、C3、D4、D7、E4、F5、H1、H6、J4、L1、L6、N1 |
| 新增 | 13 | B6、B7、C7、C8、C9、D10、E6、E7、F8、G6、H9、J7、**A7** |
| 保留 | 66 | 其余 |

四条要点：
1. **A5 最容易假通过**。原写法"空库 create_db + apply_migrations，表数一致"——只改 schema.sql 不写 migrations 也能过。真正的门禁是 `gen_models.py` 重跑后 `git diff --exit-code db/schema.sql app/models/generated.py`，且表数按 D23 改为 **55**。
2. **C1 删掉后，"能导入"的证据链全靠 C7**（job 的 `total/succeeded/failed/skipped/errors` 五字段 + `total=158`）。
3. **H6 必须拆双档**：实测全库（约 500 条）P95 < 300ms 是本期事实；合成 10 万条压力测试标 `slow`，不作业务门禁。
4. **新增 A7（D21 的机器校验）**：`for f in <6 个一期文件>; do git diff -U0 -- $f | grep -E '^-[^-]' && echo "VIOLATION: $f"; done` 必须无输出。

---

## 6 未决问题与风险（按优先级）

| # | 风险/未决 | 内容 | 建议 |
|---|---|---|---|
| R1 | ✅ **已裁决（D21）** | 白名单 6 个一期文件 + "diff 只有 `+` 行"机器校验；`AUDITOR` 落地文件更正为 `scripts/bootstrap.py`（F16），`docs/seed_all.sql` 只是快照不动 | 验收新增 A7 |
| R1b | ✅ **已裁决（D22）** | 新增角色码后端为准（`KNOWLEDGE_*` / `CS_AGENT`），前端只追加 4 个；一期前端 6 vs 7 零重叠作为已知遗留写进 N8 | design 的「一期兼容性声明」需列明 |
| R2 | ✅ **已裁决（D23 + A5）** | 迁移记录进 `shared.schema_migration`；schema.sql 保持全量真源，migrations 存增量，`gen_models.py` 重跑后无 diff；表数 55 | A5 命令已更新 |
| R3 | **C1 删除后的数量缺口** | 验收里没有任何一条断言"158 篇全部入库"，只剩 C7 的 `total=158` | 若连 C7 的 158 也不要，则需接受"能导入"仅有 C4 抽查 3 篇作为证据 |
| R4 | **pytest marker 未注册** | 仓库无 `pytest.ini`/`pyproject.toml` 配置段，`@pytest.mark.slow` 会产生 warning | D16/H6 落地前需加配置（一处新文件，属二期交付物） |
| R5 | ✅ **已裁决（D23）** | 新增第 7 张表 `shared.schema_migration`，表数 48 → **55** | A5 已同步；`shared.schema_migration` 需写进 `db/schema.sql` 与模型生成 |
| R6 | **10 万切片基准来源不明** | §8 的容量指标无需求来源 | 已按双档处理；若老板明确要求"10 万切片可用"，则二期语料体量不足以验证，需造数据或改口径 |
| R7 | ✅ **已产出（§8，25 行）** | 24 条已确认入库 + 1 条待定；含 D24 的 6 键契约与 Q-A/Q-B/Q-C 的推荐值 | design 可直接引用；Q-A/Q-B/Q-C 需老板确认后方可固化为 spec |
| R8 | **可延后项未最终拍板** | 5 项（PDF/XLSX/CSV/HTML、定时生效自动调度、治理周报快照、批注回复 UI、引用影响面分析）仍是初稿分类 | 若你确认，写进 proposal 的 out-of-scope |
| R9 | **分支现状** | 当前在 `main`，`phase2` 分支尚未创建；`openspec/`、`docs/二期/` 均为未跟踪 | 进入实现前需建 `phase2` 分支（本轮未做任何 git 操作） |

---

## 7 下一步

1. ✅ 已收口：R1 / R1b / R2 / R5（见 D21–D23）。数据模型与边界不再悬空。
2. ✅ 已产出：**R7 规则映射表**（§8，25 行 + 6 键契约 D24）。探索阶段的实质内容已全部完成。
3. 要进入实现：`/openspec-propose`，把本笔记的 **D1–D23** + §2 数据（7 张表 / 表数 55）+ §3 接口（26 路径 / 32 操作）+ §5 验收（94 条）变成 `knowledge-foundation` / `knowledge-governance` / `knowledge-retrieval-ui` 三个 change（§10 的 33 人日拆分仍成立，+1 人日 DOCX、+0.5 人日 embedding 打通）。

---

## 8 规则映射表（R7 产出，25 行）

**映射契约**（D24）：`condition` 只放"何时适用"，`action` 放"结论与参数"，`forbid` 放"禁止项"。`condition` 的键限定为 6 个；值可以是标量，也可以是标量数组（数组 = 任一命中）。

### 8.1 政策类 source_kind=policy（9 条）

| # | rule_id | condition | action | forbid | priority | conflict_group |
|---|---|---|---|---|---|---|
| 1 | `RETURN-NO-REASON-7D` | `{issue_type: return_no_reason, order_state: COMPLETED, time_window: {basis: delivery_date, max_days: 7}}` | `{decision: ALLOW_RETURN, requires: [eligible_channel, product_complete, no_unreasonable_value_loss]}` | `[]` | 100 | `return_window` |
| 2 | `QUALITY-ISSUE-RETURN-15D` | `{issue_type: quality_issue, order_state: COMPLETED, time_window: {basis: delivery_date, max_days: 15}}` | `{decision: ALLOW_RETURN, requires: [service_assessment]}` | `[]` | 100 | `return_window` |
| 3 | `QUALITY-ISSUE-EXCHANGE-30D` | `{issue_type: quality_issue, order_state: COMPLETED, time_window: {basis: delivery_date, max_days: 30}}` | `{decision: ALLOW_EXCHANGE, requires: [service_assessment]}` | `[]` | 100 | `exchange_window` |
| 4 | `REFUND-MERCHANT-PROCESS-3BD` | `{issue_type: refund, refund_state: ACCEPTED}` | `{decision: REFUND_PROCESS_DEADLINE, business_days: 3, payment_arrival_days: {wallet: "1-3", bank_card: "3-7"}}` | `[]` | 100 | `refund_sla` |
| 5 | `SHIPPING-FREE-99` | `{issue_type: shipping_fee}` | `{decision: FREE_SHIPPING, threshold_cny: 99, standard_fee_cny: 8}` | `[]` | 100 | `shipping_fee` |
| 6 | `LOGISTICS-STAGNANT-72H` | `{issue_type: logistics_stagnant, order_state: SHIPPED, time_window: {basis: last_tracking_update, max_hours: 72}}` | `{decision: RAISE_STAGNANT_ALERT}` | `[]` | 100 | `logistics_alert` |
| 7 | `ADDRESS-CHANGE-AFTER-SHIP` | `{issue_type: address_change, order_state: SHIPPED}` | `{decision: REQUEST_INTERCEPT_OR_REROUTE, guaranteed: false}` | `[]` | 100 | `address_change` |
| 8 | `INSTALL-RESCHEDULE-4H` | `{issue_type: install_reschedule}` ⚠️ | `{decision: ALLOW_RESCHEDULE, min_notice_hours: 4}` | `[]` | 100 | `install_schedule` |
| 9 | `CLOUD-COOLING-OFF-7D` | `{issue_type: cloud_cooling_off, order_state: COMPLETED, time_window: {basis: activation_date, max_days: 7}}` ⚠️ | `{decision: ALLOW_COOLING_OFF_REFUND, requires: [not_activated_or_no_cloud_recording_generated]}` | `[]` | 100 | `cloud_cooling_off` |

⚠️ 第 8、9 条：一期无"安装预约"状态机、无"设备激活时间"字段，`order_state` 按 Q-C=A 留空/存疑。

### 8.2 保修类 source_kind=warranty（7 条 + 1 条待定）

| # | rule_id | condition | action | forbid | priority | conflict_group |
|---|---|---|---|---|---|---|
| 10 | `WARRANTY-QL-L3P-MAIN-24M` | `{product_line: QL-L3P, issue_type: warranty_claim, component: lock_body_and_electronics}` | `{decision: COVER_UNDER_WARRANTY, months: 24}` | `[]` | 200 | `warranty_coverage` |
| 11 | `WARRANTY-QL-L3P-CYLINDER-24M` | `{product_line: QL-L3P, issue_type: warranty_claim, component: lock_cylinder}` | `{decision: COVER_UNDER_WARRANTY, months: 24}` | `[]` | 200 | `warranty_coverage` |
| 12 | `WARRANTY-QC-C2G-MAIN-12M` | `{product_line: QC-C2G, issue_type: warranty_claim, component: main_unit}` | `{decision: COVER_UNDER_WARRANTY, months: 12}` | `[]` | 200 | `warranty_coverage` |
| 13 | `WARRANTY-QR-R5M-MAIN-24M` | `{product_line: QR-R5M, issue_type: warranty_claim, component: robot_and_dock}` | `{decision: COVER_UNDER_WARRANTY, months: 24}` | `[]` | 200 | `warranty_coverage` |
| 14 | `WARRANTY-QR-R5M-BATTERY-12M` | `{product_line: QR-R5M, issue_type: warranty_claim, component: battery}` | `{decision: COVER_UNDER_WARRANTY, months: 12}` | `[]` | 200 | `warranty_coverage` |
| 15 | `WARRANTY-QT-L1C-MAIN-24M` | `{product_line: QT-L1C, issue_type: warranty_claim, component: lamp_and_driver}` | `{decision: COVER_UNDER_WARRANTY, months: 24}` | `[]` | 200 | `warranty_coverage` |
| 16 | `WARRANTY-QH-G1-MAIN-12M` | `{product_line: QH-G1, issue_type: warranty_claim, component: main_unit}` | `{decision: COVER_UNDER_WARRANTY, months: 12}` | `[]` | 200 | `warranty_coverage` |
| 17? | `WARRANTY-CONSUMABLE-DEFECT-ONLY`（生成 id，Q-B=A） | `{issue_type: warranty_claim, component: consumable}` | `{decision: DEFECT_ONLY, excluded_normal_wear: true}` | `[]` | 200 | `warranty_coverage` |

第 17 行来自 `product_warranty.yaml` 里**没有 `rule_id` 的 `consumables:` 块**，是 24 条之外的第 25 条候选。

### 8.3 升级类 source_kind=escalation（8 条）

| # | rule_id | condition | action | forbid | priority | conflict_group |
|---|---|---|---|---|---|---|
| 18 | `ESC-P0-TRAPPED` | `{issue_type: [person_trapped, fire, medical_emergency]}` | `{decision: ESCALATE, target: supervisor_and_emergency_guidance, response_minutes: 5}` | `[normal_troubleshooting, remote_unlock_promise]` | 1000 | `escalation` |
| 19 | `ESC-P0-ELECTRICAL` | `{issue_type: [smoke, sparks, electric_shock, battery_fire, water_near_energized_equipment]}` | `{decision: ESCALATE, target: supervisor_and_safety_team, response_minutes: 5}` | `[touch_wet_plug, move_wet_equipment, power_on_retry]` | 1000 | `escalation` |
| 20 | `ESC-P1-DEVICE-THERMAL` | `{issue_type: [abnormal_heat_without_smoke, burnt_smell_without_visible_fire, battery_swelling]}` | `{decision: ESCALATE, target: safety_and_quality_team, response_minutes: 15}` | `[continue_charging, puncture_battery, power_on_retry]` | 900 | `escalation` |
| 21 | `ESC-P1-ACCOUNT` | `{issue_type: [account_takeover, unknown_admin, credential_change]}` | `{decision: ESCALATE, target: security_team, response_minutes: 15}` | `[request_verification_code]` | 900 | `escalation` |
| 22 | `ESC-P1-CAMERA` | `{issue_type: [unknown_camera_access, unexpected_sharing]}` | `{decision: ESCALATE, target: security_and_privacy_team, response_minutes: 15}` | `[view_customer_video]` | 900 | `escalation` |
| 23 | `ESC-P1-BATCH` | `{issue_type: [batch_device_failure, cloud_region_outage]}` | `{decision: ESCALATE, target: incident_manager, response_minutes: 15}` | `[individual_compensation_promise]` | 900 | `escalation` |
| 24 | `ESC-P2-CORE` | `{issue_type: [core_function_unavailable_with_workaround]}` | `{decision: ESCALATE, target: technical_support, response_minutes: 120}` | `[]` | 600 | `escalation` |
| 25 | `ESC-P3-GENERAL` | `{issue_type: [general_question, cosmetic_issue, suggestion]}` | `{decision: ESCALATE, target: frontline_support, response_minutes: 240}` | `[]` | 300 | `escalation` |

> 已确认入库 **24 条**（1–16 + 18–25）；第 17 行待 Q-B 确认。

### 8.4 三个待老板确认的问题（已按推荐值写入上表）

| # | 问题 | 已采用 | 备选 |
|---|---|---|---|
| Q-A | 质量问题第 10 天，`ALLOW_RETURN`(15 天) 与 `ALLOW_EXCHANGE`(30 天) 同时成立时 | **客户任选**：两条分属 `return_window` / `exchange_window`，互不冲突 | 换优于退（合并 group，EXCHANGE priority 120）；退优于换（反之） |
| Q-B | `consumables:` 块要不要入库 | **入库为第 25 条**，生成 id `WARRANTY-CONSUMABLE-DEFECT-ONLY`，`source_kind=manual` | 不入库（耗材条款由文档承载） |
| Q-C | `order_state` 值域锚在哪 | **限定值为 `order_workflow.yaml` 的 7 个订单状态**；第 8/9 条留空 `order_state`，只靠 `issue_type` 匹配 | 扩值域（`INSTALL_SCHEDULED`/`ACTIVATED`）；或挂到 `time_window.basis` 枚举 |

### 8.5 两条要进 design 的事实

1. **`escalation` 的 `target` 是转人工目标**：二期只存不执行。design 必须写明"不产生任何转人工逻辑"，否则易被读成三期功能提前实现（L8）。
2. **`response_minutes`（5/15/120/240）与 `service_sla.yaml` 的 `first_response_minutes` 完全重复**：因 `service_sla.yaml` 按 D1 不入库，`escalation` 成了唯一副本。建议治理报告加一条"与 raw 文件一致性"校验，防漂移。

---

*本文件由 explore 模式产出，**不驱动实现**；实现以 OpenSpec change 为准。*
