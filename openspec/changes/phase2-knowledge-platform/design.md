# Design — 二期企业知识库平台

## Context

一期的既成事实（决定了本设计的形状，动机见 `proposal.md`）：

| 事实 | 内容 |
|---|---|
| 库 | 48 张表（shared 13 / commerce 32 / knowledge 3）；`knowledge` schema 的 3 张表为空表预留，`chunk.embedding` 是 `vector(1024)` 且已建 HNSW |
| DDL 真源 | 没有 `db/migrations/`；`db/schema.sql` 是唯一真源，`create_db.py` 整库执行；`app/models/generated.py` 由 `scripts/gen_models.py` 自动生成（文件头注明"请勿手工修改"） |
| 接口 | 89 条路径，全扁平 `/api/v1/<resource>`，无 `/admin` 前缀 |
| 隔离 | 渠道范围由服务端从 token 推导（`_channel_scope`），不信任前端传参 |
| 权限 | 表名 `shared.app_permission`；7 个角色；`AUDITOR` 按"所有 `:read`"授权 |
| 前端 | 路由已 `lazyEl` + `RequirePermission`；无任何 Markdown 渲染/编辑器依赖；`ROLE_CODES` 与后端角色码零重叠 |
| 语料 | 158 篇 md（644KB，`##` 285 个）+ 10 个规则 yaml + 1 个校验脚本；预计切片 400–600 |
| 依赖 | 无 torch / sentence-transformers / numpy / python-docx；HF 缓存里没有 `bge-small-zh-v1.5` |

## Goals / Non-Goals

**Goals**

- 一期兼容性可用**一条命令**校验，而不是靠人工承诺。
- `db/schema.sql`、`db/migrations/`、`app/models/generated.py` **三者永不漂移**。
- 结构化规则与文档**分治**：规则是精确真源，文档是检索卡片，二者不共用召回通道。
- 检索能力**只有一个 HTTP 入口**，但有两段语义：稳定引用与调试信息。
- 在"单人开发 + 阶段串行"的前提下，每条验收都能用一条命令出证据。

**Non-Goals**

- 不设计三/四期的会话、生成、本体、工具与评测（只留字段、服务边界、事件出口）。
- 不做多知识库空间或多租户分区（沿用 `(tenant_id, document_id)` 唯一键）。
- 不做 PDF / XLSX / CSV / HTML 的版面解析。
- 不做规则运行时求值、策略编排、意图识别。

## Decisions

### 决策 1：一期兼容用「白名单 + 纯追加」的机器校验

白名单共 **9 个**一期文件，分两类约束。

**A 类：只允许纯追加**（`git diff` 只有 `+` 行，无 `-` 行）

| 文件 | 追加内容 |
|---|---|
| `app/api/v1/router.py` | `include_router(knowledge.router)` |
| `app/integrations/storage.py` | `ALLOWED` 加 `.md`、`.yaml` |
| `requirements.txt` | 追加 `pgvector`、`numpy`、`python-docx`、`sentence-transformers`、`torch`、`PyYAML` |
| `app/core/middleware.py` | 幂等豁免前缀追加知识库预览与导入（原常量保留，追加一行扩展） |
| `web/src/constants/routes.ts` | 7 个路由常量 |
| `web/src/types/permissions.ts` | 12 个权限码 + 4 个角色码 + `P` 的 12 个键 |
| `web/src/layouts/AdminShell.tsx` | `MENU` 加一个分组 |

**B 类：工具与测试，允许改既有行**

| 文件 | 改动 |
|---|---|
| `scripts/gen_models.py` | schema 过滤加 `knowledge`；跳过生成列；`metadata` 属性改名 `metadata_json`（列名不变）；`vector(n)` 映射为 `Vector` |
| `tests/test_model_consistency.py` | schema 过滤加 `knowledge`；DDL 列集合跳过 `GENERATED ALWAYS AS` |
| `scripts/bootstrap.py` | 追加 12 个权限码与 4 个角色；`CS_SUPERVISOR` 授权并入知识只读；`READ_ONLY` 展开排除 `knowledge:%`。改既有行是因为角色授权是既有列表数据，且审计员的收窄必须落在生成逻辑里，否则重跑 seed 会把权限放回来 |

B 类之所以必须改既有行：一期 `gen_models.py` 与 `test_model_consistency.py` **显式排除 knowledge schema**（`if schema not in ("shared","commerce")`），而二期要让 9 张知识表进入 ORM；同时 `metadata` 与 SQLAlchemy Declarative 的保留属性冲突、`tsv` 是生成列不能映射。二者都是工具/测试，零运行时影响——改后一期 53 项测试全部保持通过。

校验命令：

```bash
# A 类：不得出现删除行
for f in app/api/v1/router.py app/integrations/storage.py requirements.txt app/core/middleware.py \
         web/src/constants/routes.ts web/src/types/permissions.ts web/src/layouts/AdminShell.tsx; do
  git diff -U0 -- "$f" | grep -E '^-[^-]' && echo "VIOLATION: $f"
done

# B 类：改动面必须落在上述四项之内（人工核对 + 一期回归）
git diff --stat -- scripts/gen_models.py tests/test_model_consistency.py scripts/bootstrap.py
python -m pytest -q   # 一期 53 项必须全绿
```

**备选与否决**：*零触碰* 需要先把一期改成插件式注册（+2 人日且改一期架构），而 `include_router` 一行躲不掉，且 knowledge schema 的排除同样躲不掉；*宽口径*（只禁表结构/接口/类型语义）会失去可审计性。

### 决策 2：迁移三一致

- `db/schema.sql` 保持**全量真源**（空库一步建成 55 张表）。
- `db/migrations/000X_*.sql` 存**增量**（既有库升级），由 `scripts/apply_migrations.py` 顺序执行、按 `shared.schema_migration.checksum` 判重、可重复执行。
- 每次改 DDL 后**重跑** `scripts/gen_models.py`，不手写模型。
- 门禁：`gen_models.py` 后 `git diff --exit-code db/schema.sql app/models/generated.py` 必须为空。

**备选与否决**：*只改 schema.sql* 无法升级已在跑的库；*引入 Alembic* 一期未用，且会把迁移从 SQL 变成 Python，破坏"DDL 为唯一事实源"。

### 决策 3：数据模型

**改列**：`knowledge.chunk.embedding` 1024 → 512，重建 `hnsw (vector_cosine_ops) with (m=16, ef_construction=64)`。表内无数据，安全；`docs/schema.sql` 与 `db/schema.sql` 两份同源文件必须同步。

**加列（9 个，0 个改约束）**

| 表 | 列 | 说明 |
|---|---|---|
| `knowledge.chunk` | `embedding_status` | PENDING/READY/FAILED，默认 PENDING |
| `knowledge.chunk` | `identity_level` | public/customer/agent，默认 public |
| `knowledge.document` | `identity_level`、`effective_date` | 其余（region/tags）放 `metadata jsonb` |
| `knowledge.document_version` | `change_summary`、`published_at`、`published_by`、`source_kind` | 发布信息与规则来源 |

**不改约束**：`knowledge.document.status` 的 CHECK 保持一期取值（DRAFT/REVIEWING/ACTIVE/ARCHIVED/FAILED）。"待生效"只落在 `document_version.status`（该表枚举已含 SCHEDULED），`document.status` 语义为"有生效版本"。

**新增 7 张表**

| 表 | 关键列 |
|---|---|
| `knowledge.rule` | `rule_id`(唯一，原生 id)、`source_kind`、`condition jsonb`、`action jsonb`、`forbid jsonb`、`priority`、`status`、`effective_from/until`、`conflict_group`、`source_file`、`source_line`、`tenant_id`、审计列 |
| `knowledge.rule_conflict` | `rule_a`、`rule_b`、`conflict_type`、`severity`、`status`、`detected_at`、`resolved_by/at` |
| `knowledge.review_task` | `document_version_id`、`assignee_id`、`status`、`due_at`、`decision`、`decided_at`、`note`、`self_review` |
| `knowledge.review_comment` | `version_id`、`author_id`、`anchor jsonb`、`content`、`resolved`、`parent_id` |
| `knowledge.import_job` | `source_type`、`file_name`、`checksum`、`status`、`total`、`succeeded`、`failed`、`skipped`、`errors jsonb`、`idempotency_key` |
| `knowledge.retrieval_log` | `query`、`filters jsonb`、`top_k`、`hits jsonb`、`latency_ms`、`actor_id`、`identity_level`、`hit_count`、`kind` |
| `shared.schema_migration` | `version`、`file_name`、`checksum`、`applied_at`、`applied_by`、`duration_ms`、`success` |

表数：48 → **55**（shared 14 / commerce 32 / knowledge 9）。

**索引策略**：沿用一期 HNSW + `gin(tsv)` + `gin(trgm)`；`identity_level` **不建单列索引**——取值只有 3 个、基数极低，且总与状态/租户条件一起过滤，单列索引无收益。数据量显著增长后再评估部分索引。

### 决策 4：结构化规则与六键契约

`condition` 只放"何时适用"，`action` 放"结论与参数"，`forbid` 放"禁止项"。`condition` 键限定为 6 个：`product_line`、`issue_type`、`order_state`、`identity_level`、`time_window`、`component`；值可为标量或标量数组（数组 = 任一命中）。落库前校验键集合，非法键直接拒绝。

**为什么是 6 键而不是需求文档的 5 键**：保修类里 `QL-L3P` 有主机/锁芯两条、`QR-R5M` 有主机/电池两条，`product_line` 与 `issue_type` 完全相同。`component` 一旦不在条件里，这 4 条会被判成"同条件、结论不一致"→ 误报阻断 → 发布门禁第一天就死锁。

**25 条规则映射**（24 条已确认入库；第 17 行为待定候选）

| # | rule_id | 条件 | 结论 | 禁止项 | 优先级 | 冲突组 |
|---|---|---|---|---|---|---|
| 1 | `RETURN-NO-REASON-7D` | return_no_reason + COMPLETED + 签收后≤7天 | ALLOW_RETURN | — | 100 | return_window |
| 2 | `QUALITY-ISSUE-RETURN-15D` | quality_issue + COMPLETED + 签收后≤15天 | ALLOW_RETURN | — | 100 | return_window |
| 3 | `QUALITY-ISSUE-EXCHANGE-30D` | quality_issue + COMPLETED + 签收后≤30天 | ALLOW_EXCHANGE | — | 100 | exchange_window |
| 4 | `REFUND-MERCHANT-PROCESS-3BD` | refund + 退款 ACCEPTED | REFUND_PROCESS_DEADLINE（3 工作日，到账 1–3/3–7 天） | — | 100 | refund_sla |
| 5 | `SHIPPING-FREE-99` | shipping_fee | FREE_SHIPPING（满 99 免运费，否则 8 元） | — | 100 | shipping_fee |
| 6 | `LOGISTICS-STAGNANT-72H` | logistics_stagnant + SHIPPED + 轨迹 72 小时未更新 | RAISE_STAGNANT_ALERT | — | 100 | logistics_alert |
| 7 | `ADDRESS-CHANGE-AFTER-SHIP` | address_change + SHIPPED | REQUEST_INTERCEPT_OR_REROUTE（不保证成功） | — | 100 | address_change |
| 8 | `INSTALL-RESCHEDULE-4H` | install_reschedule（订单状态留空） | ALLOW_RESCHEDULE（≥4 小时通知） | — | 100 | install_schedule |
| 9 | `CLOUD-COOLING-OFF-7D` | cloud_cooling_off + 激活后≤7天 | ALLOW_COOLING_OFF_REFUND | — | 100 | cloud_cooling_off |
| 10 | `WARRANTY-QL-L3P-MAIN-24M` | QL-L3P + warranty_claim + lock_body_and_electronics | COVER 24 个月 | — | 200 | warranty_coverage |
| 11 | `WARRANTY-QL-L3P-CYLINDER-24M` | QL-L3P + warranty_claim + lock_cylinder | COVER 24 个月 | — | 200 | warranty_coverage |
| 12 | `WARRANTY-QC-C2G-MAIN-12M` | QC-C2G + warranty_claim + main_unit | COVER 12 个月 | — | 200 | warranty_coverage |
| 13 | `WARRANTY-QR-R5M-MAIN-24M` | QR-R5M + warranty_claim + robot_and_dock | COVER 24 个月 | — | 200 | warranty_coverage |
| 14 | `WARRANTY-QR-R5M-BATTERY-12M` | QR-R5M + warranty_claim + battery | COVER 12 个月 | — | 200 | warranty_coverage |
| 15 | `WARRANTY-QT-L1C-MAIN-24M` | QT-L1C + warranty_claim + lamp_and_driver | COVER 24 个月 | — | 200 | warranty_coverage |
| 16 | `WARRANTY-QH-G1-MAIN-12M` | QH-G1 + warranty_claim + main_unit | COVER 12 个月 | — | 200 | warranty_coverage |
| 17? | `WARRANTY-CONSUMABLE-DEFECT-ONLY` | warranty_claim + consumable | DEFECT_ONLY | — | 200 | warranty_coverage |
| 18 | `ESC-P0-TRAPPED` | 人员被困 / 火情 / 医疗急症 | ESCALATE → 主管与紧急指导，5 分钟 | 常规排障、承诺远程开锁 | 1000 | escalation |
| 19 | `ESC-P0-ELECTRICAL` | 冒烟 / 火花 / 触电 / 电池起火 / 水浸带电 | ESCALATE → 主管与安全团队，5 分钟 | 触碰湿插头、移动浸水设备、通电重试 | 1000 | escalation |
| 20 | `ESC-P1-DEVICE-THERMAL` | 异常发热无烟 / 焦味无明火 / 电池鼓包 | ESCALATE → 安全与质量团队，15 分钟 | 继续充电、穿刺电池、通电重试 | 900 | escalation |
| 21 | `ESC-P1-ACCOUNT` | 账号被盗 / 未知管理员 / 凭证变更 | ESCALATE → 安全团队，15 分钟 | 索取验证码 | 900 | escalation |
| 22 | `ESC-P1-CAMERA` | 未知摄像头访问 / 异常分享 | ESCALATE → 安全与隐私团队，15 分钟 | 查看客户视频 | 900 | escalation |
| 23 | `ESC-P1-BATCH` | 批量设备故障 / 云区域故障 | ESCALATE → 事故经理，15 分钟 | 承诺个体赔偿 | 900 | escalation |
| 24 | `ESC-P2-CORE` | 核心功能不可用但有绕过 | ESCALATE → 技术支持，120 分钟 | — | 600 | escalation |
| 25 | `ESC-P3-GENERAL` | 一般咨询 / 外观问题 / 建议 | ESCALATE → 一线客服，240 分钟 | — | 300 | escalation |

**冲突判定**：同一 `conflict_group` 内，两条生效规则**条件相交**（键值有交集、`time_window` 区间重叠）且 **结论互斥**（`ALLOW_*` 对 `DENY_*`、`COVER` 对 `NOT_COVER`、`FREE` 对 `CHARGE`）→ 阻断级；条件相交但结论不同且不互斥（如 `ALLOW_RETURN` 对 `ALLOW_EXCHANGE`）→ 提醒级。**备选**：无条件 BLOCK 会把第 2/3 条误判，导致门禁常态化失败。

**规则不参与向量召回**：规则是精确真源，用向量近似召回会违反知识库自己的"真源优先级"与"不得自行选择"条款。规则只经结构化查询对外。

### 决策 5：切片与向量化流水线

- **切片**：标题栈按层级切；单片 200–600 字符，超长按段落二次切；表格转「表头: 值」并保留行号；有序步骤保留序号；问答对按 Q/A 成对切。`title_path` 形如「一级 / 二级」。`token_count` 按字符数近似（中文 1 字≈1 token），用于预算与截断。
- **状态机**：切片先落库 `PENDING` → worker 取任务（`FOR UPDATE SKIP LOCKED`）→ `READY`；异常置 `FAILED` 并累加 `retry_count`，超过上限停止重试。检索只取 `READY`。
- **worker 双形态**：常驻轮询 + `--once` 跑一轮退出。验收里的"到点生效""补齐向量""失败重试"都变成一条命令，不需要挂常驻进程。
- **模型**：`BAAI/bge-small-zh-v1.5`，512 维，L2 归一化，cosine。**入库的切片不加指令前缀，查询侧加**「为这个句子生成表示以用于检索相关文章：」（bge 系列既定用法）。模型位置：默认 `HF_HOME=var/models` 自动下载（约 95MB）；配置 `EMBEDDING_MODEL_PATH` 时离线直用。进程内单例懒加载。
- **重算**：`scripts/reindex_embeddings.py --batch N`，按 id 区间分批，中断后从 `PENDING/FAILED` 继续，已 `READY` 的不重复处理。

### 决策 6：检索设计

- **一次检索的过滤条件**（全部 AND）：版本 `status='ACTIVE'`、`effective_until` 为空或不早于 `now()`、`embedding_status='READY'`、`tenant_id`、渠道范围交集、产品/业务域、`identity_level`（默认 `public`）。
- **两路召回**：全文路用 `plainto_tsquery('simple', …)` 走 `tsv` 索引，并用 `similarity(content, …)` 兜底；向量路用 `embedding <=> query_vec` 走 HNSW 取最近 N。
- **融合**：服务层做 RRF（`k=60`），两路各取 `max(top_k*4, 20)` 候选。**备选**：单条 SQL 内 CTE 融合——省一次往返，但两路参数难独立调整、EXPLAIN 难读、单测难替换。
- **阈值**：相似度 `1 - (embedding <=> query_vec) < 0.35` 丢弃，不为凑满 TopK 返回低相关。
- **响应分段**：`{hits: [...], debug: {...}}`。`hits` 是稳定引用契约（document_id / version / title_path / line_start / line_end / chunk_ord / snippet），`debug` 只有分数与耗时，明确标注"仅供调试、三期勿依赖"。
- **服务层**：`app/services/knowledge_retrieval.py` 暴露 `search(db, query, filters, top_k, actor)`，路由只做参数校验、权限与日志。三期在进程内直接 import，**不预置 HTTP 服务身份**。
- **日志**：每次调用写 `retrieval_log`，`kind` 区分 test / prod。

### 决策 7：身份与权限

- **12 个权限码**：`knowledge:document:{read,write,import,archive,publish,rollback}`、`knowledge:rule:{read,write}`、`knowledge:review:{read,write}`、`knowledge:retrieval:test`、`knowledge:governance:read`，登记到 `shared.app_permission`（`module='knowledge'`）。
- **4 个新角色**：`KNOWLEDGE_ADMIN`、`KNOWLEDGE_REVIEWER`、`KNOWLEDGE_EDITOR`、`CS_AGENT`；`CS_SUPERVISOR` 复用一期角色，只追加授权。
- **AUDITOR 收窄**：既在 migration 里删除已有绑定，也在 `bootstrap.py` 的 `READ_ONLY` 展开条件里排除 `knowledge:%`——否则 `create_db --reset` + `seed` 会把权限放回来。
- **前端命名**：`ROLE_CODES` 只**追加** 4 个新码；一期"前端 6 个角色码 vs 后端 7 个，零重叠"作为已知遗留不动，记入二期总结。

### 决策 8：导入通道

- **一次请求多文件** `multipart`（158 个 md 共约 644KB，远低于 20MB/文件上限），不做 zip、不做服务端目录扫描。
- **扩展名白名单**：在 `storage.ALLOWED` 追加 `.md`、`.yaml`，其余沿用一期（含 20MB 上限、MIME 比对、magic 校验、sha256）。
- **规则 YAML 走独立入口**：只接受政策 / 保修 / 升级 3 类，其他形态返回 400 并说明"该形态不纳管"。
- **DOCX**：`python-docx` 抽段落与表格，表格转「表头: 值」。**已知限制**：语料里没有真实 DOCX，解析只能靠 fixture 验证。

### 决策 9：前端

- 7 个路由全部 `lazyEl`，不新增首屏体积；`AdminShell.MENU` 加一个"知识库"分组。
- 编辑器 = antd `Input.TextArea` + `react-markdown` **只读预览**；切片预览调 `POST /knowledge/preview-chunks`，停止输入 500ms 防抖。**不引入编辑器框架**（`@uiw/react-md-editor` 一类）。
- 发布弹窗统一组件：变更摘要 / 影响范围 / 引用数量（本期恒 0）/ 回滚目标 / 自审标记。

### 决策 10：测试与契约

- **向量测试双层**：多数测试用确定性 fake embedder（同文本→同向量、512 维、归一化）；仅 1 条真模型 smoke 标 `@pytest.mark.slow`。当前仓库无 pytest 配置段，需新增 `pytest.ini`（注册 `slow`）。
- **契约门禁**：改接口后必跑 `python scripts/export_openapi.py` + `python scripts/check_frontend_contract.py`（后者只校验路径与方法，字段对齐靠 `response_model` 与前端类型生成）。
- **三阶段闸门**：见 `tasks.md` 每组末尾的闸门任务，闸门不通过不得进入下一组。

## Risks / Trade-offs

| 风险 | 缓解 |
|---|---|
| `vector(1024)→512` 改列不可逆 | 表内无数据；`docs/schema.sql` 与 `db/schema.sql` 双写；迁移文件附带反向语句注释 |
| 语料仅约 500 条切片，与"10 万切片"指标差两个数量级 | 验收拆双档：本期实测（约 500 条）P95 < 300ms 为业务门禁；10 万条为合成压力测试，标 `slow`、只记录不门禁 |
| 单 change 合并交付，中途无归档节点 | 三组任务各设阶段闸门，闸门 = 对应验收子集全绿 |
| 一期前端角色码与后端零重叠 | 本期不修，只追加 4 个新码；写入二期总结作为已知遗留 |
| 首次需下载 95MB 模型 | 默认自动下载到 `var/models`；`EMBEDDING_MODEL_PATH` 支持离线；运维文档写明获取步骤 |
| 无真实 DOCX 素材 | 解析器用 fixture 验证；不假装有业务素材 |
| 两路检索各一次 SQL 往返 | 语料 500 条量级可接受；若将来变慢，再合并为单条 CTE |
| 规则冲突算法若过于激进会常态阻断 | 结论互斥才 BLOCK，否则 WARN（见决策 4） |

## Migration Plan

1. 建本地分支 `phase2`（`main` 保持一期快照），全程不 push。
2. 改 `db/schema.sql`：改列 + 9 加列 + 7 建表 + 索引重建。
3. 写 `db/migrations/0001..000N_*.sql`；新增 `scripts/apply_migrations.py`。
4. 重跑 `scripts/gen_models.py`，确认无手写残留。
5. 追加权限码与角色授权；收窄 `AUDITOR`；同步 `scripts/bootstrap.py`。
6. 安装新增依赖，首次运行下载模型到 `var/models`。
7. 空库验收：`create_db.py --reset --force` → `apply_migrations.py` → 表数 55 → `gen_models` 无 diff。
8. 导入 158 篇 md + 3 类规则 yaml → 跑 worker `--once` → 抽查切片与向量。
9. **回滚策略**：代码回滚到 `main`；库回滚依赖库重建（无生产数据）。若已在有数据环境升级过，执行迁移文件尾部的反向语句并删除 `shared.schema_migration` 对应行。

## Open Questions

以下三项只影响**种子数据的取值**，不改变 specs、方案或任务拆分，可在实施对应任务前拍板：

1. 质量问题第 10 天时，`ALLOW_RETURN`(15 天) 与 `ALLOW_EXCHANGE`(30 天) 同时成立——是"客户任选"（当前设计：二者分属不同冲突组，均返回）还是"换优于退"？
2. `product_warranty.yaml` 里无 `rule_id` 的 `consumables` 块要不要成为第 25 条规则？
3. 规则条件的 `order_state` 值域是否严格限定为订单工作流定义的 7 个状态（当前设计：是；第 8/9 条因此留空 `order_state`）。

另有两项不影响本期实现：PDF/XLSX 导入何时做；"10 万切片"指标的正式口径。
