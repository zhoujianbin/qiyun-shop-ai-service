# Tasks

> 三组阶段闸门：CH1 = 组 1–3，CH2 = 组 4–6，CH3 = 组 7–9；组 10 为归档前集成检查。
> 每条任务的"验证"必须当场可执行，不通过不得勾选。

## 1. 基础设施与迁移（CH1）

- [x] 1.1 建本地分支 `phase2` 并确认 `main` 保持一期快照；验证：`git branch --show-current` 输出 `phase2`，`git log main --oneline -1` 仍是一期提交
- [x] 1.2 改 `db/schema.sql`：`knowledge.chunk.embedding` 由 `vector(1024)` 改为 `vector(512)`，并重建 `hnsw (vector_cosine_ops) with (m=16, ef_construction=64)`；验证：新建空库后 `\d knowledge.chunk` 显示 512 与 hnsw 索引
- [x] 1.3 在 `db/schema.sql` 为 `chunk` 增加 `embedding_status`、`identity_level`，为 `document` 增加 `identity_level`、`effective_date`，为 `document_version` 增加 `change_summary`、`published_at`、`published_by`、`source_kind`（共 9 列，不动任何既有 CHECK）；验证：`\d` 三张表可见全部新列，`document.status` 的 CHECK 与一期完全一致
- [x] 1.4 在 `db/schema.sql` 新建 7 张表（`knowledge.rule`、`rule_conflict`、`review_task`、`review_comment`、`import_job`、`retrieval_log`、`shared.schema_migration`）与必要索引；验证：`select count(*) from information_schema.tables where table_schema in ('shared','commerce','knowledge') and table_type='BASE TABLE'` 返回 55（该 schema 下另有 3 个视图，不加过滤会数到 58）
- [x] 1.5 同步 `docs/schema.sql`；验证：`diff db/schema.sql docs/schema.sql` 无输出
- [x] 1.6 写 `db/migrations/0001`–`000N` 增量 DDL（含 AUDITOR 授权收回），每条附幂等写法与回滚注释；验证：把一期空库升级后表数同样为 55
- [x] 1.7 写 `scripts/apply_migrations.py`：顺序执行、按 checksum 判重、单文件事务、失败即停；验证：连续执行两次，第二次全部 skipped 且退出码 0
- [x] 1.8 重跑 `scripts/gen_models.py` 生成 ORM；验证：`git diff --exit-code app/models/generated.py` 在无手写改动时为空
- [x] 1.9 追加 12 个 `knowledge:*` 权限码与 4 个角色授权，并在 `scripts/bootstrap.py` 的 READ_ONLY 展开中排除 `knowledge:%`；验证：`select code from shared.app_permission where module='knowledge'` 返回 12 行，且 AUDITOR 的 knowledge 读权限查询返回 0 行
- [x] 1.10 在 `requirements.txt` 追加 `sentence-transformers`、`torch`（CPU）、`numpy`、`python-docx`；新增 `pytest.ini` 注册 `slow` 标记；验证：`pip install -r requirements.txt` 成功，`python -m pytest --markers` 列出 `slow`
- [x] 1.11 为迁移与权限写自动化测试（表数 55、9 个新列存在、12 个权限码、AUDITOR 无 knowledge 读权限）；验证：`python -m pytest -q tests/test_knowledge_schema.py` 全绿
- [x] 1.12 更新 `docs/知识库运维.md` 的迁移章节（空库流程、升级流程、回滚方式）；验证：按文档命令在空库完整走通一次

## 2. 向量适配器（CH1）

- [x] 2.1 实现 `app/integrations/embedding.py`：`BAAI/bge-small-zh-v1.5`，512 维，L2 归一化，进程内单例懒加载；模型默认下载到 `var/models`，`EMBEDDING_MODEL_PATH` 可指定离线路径；验证：首次调用后 `var/models` 出现模型文件，二次调用不重复加载
- [x] 2.2 实现确定性 fake embedder（同文本→同向量、512 维、归一化）供测试注入；验证：同一文本两次调用向量完全相同且模长为 1
- [x] 2.3 实现查询侧指令前缀（「为这个句子生成表示以用于检索相关文章：」），入库侧不加前缀；验证：单测断言查询向量与入库向量在有无前缀时不同
- [x] 2.4 写 1 条真模型 smoke 测试并标 `@pytest.mark.slow`；验证：`python -m pytest -q -m slow` 可单独跑通
- [x] 2.5 在 `docs/知识库运维.md` 记录模型获取、离线部署与更换模型的维度影响；验证：文档中的离线路径配置按原样可用

## 3. 导入与切片（CH1）

- [x] 3.1 在 `app/integrations/storage.py` 的 `ALLOWED` 追加 `.md`、`.yaml`（纯追加，不改既有行）；验证：`git diff -U0 -- app/integrations/storage.py` 只有 `+` 行
- [x] 3.2 实现文档解析器：Markdown / TXT / DOCX（段落与表格），解析 front matter 的 7 个必填字段；验证：抽查 3 篇原文，解析结果与 front matter 一致；缺 `document_id` 的文件进错误清单
- [x] 3.3 实现切片器：按标题层级、单片 200–600 字符、超长按段落二次切、表格转「表头: 值」、保留 `title_path` 与原文起止行号；验证：抽查切片 `title_path` 形如「一级 / 二级」，字符数 ≤600，按行号回读原文一致
- [x] 3.4 实现导入任务：一次请求多文件、sha256 去重、`Idempotency-Key` 幂等、单文件失败不阻塞、错误清单落库；验证：二次导入同一批文件时文档数不变且 `skipped` > 0；同键重试返回同一任务号
- [x] 3.5 实现接口 `POST /knowledge/import/jobs`、`GET /knowledge/import/jobs/{id}`、`POST /knowledge/preview-chunks`，全部带 `response_model`；验证：一次请求上传 158 个 md 返回 `total=158`，五个结果字段齐全
- [x] 3.6 实现向量化 worker：`FOR UPDATE SKIP LOCKED` 取 `PENDING` 切片、写回 `READY`，异常置 `FAILED` 并累加重试次数；支持常驻与 `--once` 两种形态；验证：导入后切片为 `PENDING`，执行 `--once` 后变 `READY`；注入异常后为 `FAILED`，重试后恢复
- [x] 3.7 实现 `scripts/reindex_embeddings.py --batch N`：按 id 区间分批、可断点续跑、不重复处理 `READY`；验证：中途中断后重跑，最终全部切片为 `READY` 且行数不变
- [x] 3.8 为导入与切片写测试（格式、去重、幂等、失败隔离、切片长度、行号、向量状态、512 维与模长、重算）；验证：`python -m pytest -q tests/test_knowledge_import.py tests/test_knowledge_chunk.py` 全绿
- [x] 3.9 在 `docs/知识库运维.md` 补导入章节：支持格式、单文件上限、批量上限、规则 YAML 的纳管范围、失败样例；验证：文档所列命令按原样执行通过
- [x] 3.10 **闸门 CH1**：跑 A5–A7、B1–B7、C2–C9、F1–F8 全部验收子集；验证：每条有命令与输出证据，任一不过则不得进入组 4

## 4. 结构化规则（CH2）

- [x] 4.1 实现规则 YAML 映射器：政策 9 条、保修 7 条、升级 8 条共 24 条落库，`source_kind` 分别记为 policy / warranty / escalation；验证：`select source_kind,count(*) from knowledge.rule group by 1` 返回 9/7/8
- [x] 4.2 实现 6 键条件校验（`product_line`、`issue_type`、`order_state`、`identity_level`、`time_window`、`component`，值可为标量或数组）；验证：使用六键之外的键建规则返回 422 并指出非法键名
- [x] 4.3 实现规则接口 `GET/POST /knowledge/rules`、`GET/PATCH /knowledge/rules/{id}`、`POST /knowledge/rules/import`，`rules/import` 只接受三类 YAML；验证：导入意图分类 YAML 返回 400 且说明"该形态不纳管"
- [x] 4.4 实现冲突检测：同冲突组内条件相交且结论互斥判阻断级，结论不同但不互斥判提醒级；实现 `POST /knowledge/rules/check-conflicts`、`GET /knowledge/rule-conflicts`、`PATCH /knowledge/rule-conflicts/{id}`；验证：构造两条互斥规则后检测返回 BLOCK，标记已解决后状态为 RESOLVED 且记录解决人与时间
- [x] 4.5 为规则写测试（来源分布、六键校验、冲突 BLOCK/WARN、解决、过期规则不参与检测、规则不进入检索结果）；验证：`python -m pytest -q tests/test_knowledge_rule.py` 全绿
- [x] 4.6 在 `docs/知识库运维.md` 记录规则键契约与 25 行映射表；验证：文档中的 rule_id 与库内数据逐条一致

## 5. 版本与发布（CH2）

- [x] 5.1 实现版本状态机与 `POST /knowledge/versions/{id}/submit`：草稿→审核中并生成审核任务；验证：提交后版本状态为 REVIEWING，`knowledge.review_task` 新增一行
- [x] 5.2 实现 `POST /knowledge/versions/{id}/publish`：旧生效版本转归档、目标版本转生效、`document.current_version` 同步；验证：任一文档处于生效状态的版本数恒为 1
- [x] 5.3 实现定时生效：`effective_from` 在未来时版本进入 SCHEDULED，worker 到点转 ACTIVE，`document.status` 不使用 SCHEDULED；验证：设为 1 分钟后执行 `knowledge_worker.py --once`，状态由 SCHEDULED 变 ACTIVE
- [x] 5.4 实现 `POST /knowledge/versions/{id}/rollback`：生成新版本、内容复制、版本号递增、历史保留；验证：回滚后内容与目标版本一致，历史版本行数不变
- [x] 5.5 实现发布门禁（切片为空 / checksum 未变 / 必填元数据缺失 / 未解决阻断级冲突）与发布信息返回（变更摘要、影响范围、引用数量恒 0、回滚目标）；验证：四种情形分别返回原因清单；正常发布返回四项信息
- [x] 5.6 为写操作接入审计与领域事件（发布 / 归档 / 回滚 / 切片完成）；验证：任一写操作的 `request_id` 可在 `shared.audit_log` 反查；`shared.outbox_event` 出现对应 `knowledge.*` 事件
- [x] 5.7 为版本与发布写测试（状态机、单一 ACTIVE、定时、回滚、门禁、发布信息、审计、事件）；验证：`python -m pytest -q tests/test_knowledge_publish.py` 全绿

## 6. 审核与自审（CH2）

- [x] 6.1 实现审核队列与认领：`GET /knowledge/review/tasks`、`GET /knowledge/review/tasks/{id}`、`POST .../claim`，认领互斥；验证：两个身份先后认领同一任务，第二次失败
- [x] 6.2 实现批注：`GET/POST /knowledge/review/tasks/{id}/comments`，锚点支持标题路径 / 切片序号 / 字符区间，可标记已解决；验证：对某切片建批注后能定位到该切片与原文位置
- [x] 6.3 实现决定：`POST .../decide`，通过 / 退回 / 拒绝必须带理由，理由缺失返回 422 且不改状态；验证：缺理由时状态不变
- [x] 6.4 实现自审策略：配置 `knowledge.allow_self_review`（默认开），自审时写 `self_review=true` 并在发布信息与审计中可见；关闭后同一人审核返回 409；验证：两种配置各跑一次
- [x] 6.5 为审核写测试（队列可见、认领互斥、锚定、理由校验、状态驱动、自审标记）；验证：`python -m pytest -q tests/test_knowledge_review.py` 全绿
- [x] 6.6 **闸门 CH2**：跑 D1–D10、E1–E7、G1–G6 全部验收子集；验证：每条有命令与输出证据，任一不过则不得进入组 7

## 7. 检索（CH3）

- [x] 7.1 实现 `app/services/knowledge_retrieval.py::search(db, query, filters, top_k, actor)`：过滤条件为生效版本、未过期、向量就绪、租户、渠道交集、产品/业务域、身份等级；验证：进程内直接调用（不经 HTTP）返回结构化结果
- [x] 7.2 实现两路召回（`plainto_tsquery('simple', …)` + `similarity` 兜底、`embedding <=> query_vec`）与服务层 RRF 融合（k=60），相似度低于 0.35 丢弃；验证：无关查询返回空或少于上限
- [x] 7.3 实现响应分段：`hits`（document_id / version / title_path / line_start / line_end / chunk_ord / snippet）与 `debug`（三路分数 + 耗时），`hits` 内不含分数；验证：单测断言 `hits[0]` 键集合不含 `*_score`
- [x] 7.4 实现 `POST /knowledge/retrieval/test` 并写入 `retrieval_log`（query / filters / top_k / hit_count / latency_ms / actor_id / identity_level / kind）；验证：一次调用后日志新增一行且字段完整
- [x] 7.5 实现 `identity_level` 过滤（默认 public）：手工插入一条 agent 级切片验证可证伪；验证：默认检索不返回该切片，显式传 agent 时返回
- [x] 7.6 为检索写测试（过滤、过期、隔离收窄与 404、融合、阈值、引用字段、分段、日志、进程内调用、规则不参与、身份等级）；性能双档：本期实测 P95 < 300ms 为门禁，10 万条合成为 `slow` 仅记录；验证：`python -m pytest -q tests/test_knowledge_retrieval.py` 全绿
- [x] 7.7 在 `docs/知识库运维.md` 补"检索服务调用约定"（供三期直接 import 的签名、返回结构、调试段不得依赖）；验证：按文档写的最小示例可运行

## 8. 治理与概览（CH3）

- [x] 8.1 实现 `GET /knowledge/governance/report`：重复、过期、孤立、冲突、与 `commerce.product.model_code` 不一致五类；验证：人为各造一条数据后报告能分别列出
- [x] 8.2 实现 `GET /knowledge/overview`：文档数、待审、过期、冲突、切片数；验证：概览数字与对应列表总数相等
- [x] 8.3 实现报告下钻（携带过滤条件跳转文档列表）；验证：点击任一报告项进入的列表带对应过滤且总数与报告一致
- [x] 8.4 为治理写测试（五类有数据、下钻带过滤、概览与列表一致）；验证：`python -m pytest -q tests/test_knowledge_governance.py` 全绿

## 9. 前端（CH3）

- [x] 9.1 在 `web/src/constants/routes.ts`、`web/src/types/permissions.ts`、`web/src/layouts/AdminShell.tsx` 做纯追加：7 个路由常量、12 个权限码、12 个 `P` 键、4 个角色码、1 个菜单分组；验证：三个文件的 `git diff -U0` 只有 `+` 行
- [x] 9.2 新增 `web/src/api/endpoints/knowledge.ts` 封装全部二期接口（路径为字面量，供契约脚本扫描）与 `web/src/types/knowledge.ts` 类型；验证：`npx tsc --noEmit` 无错误
- [x] 9.3 实现概览页与文档列表页（筛选、批量归档入口、导入入口），复用一期 `EmptyState/ErrorState/LoadingSkeleton`；验证：两个路由渲染成功，筛选参数进入 URL
- [x] 9.4 实现文档详情页（元数据侧栏、版本时间线、切片预览、发布与回滚入口）；验证：详情页能展示当前版本与元数据，切片分页可翻页
- [x] 9.5 实现编辑器页：`Input.TextArea` + `react-markdown` 只读预览，切片预览走 `POST /knowledge/preview-chunks` 且 500ms 防抖；验证：停止输入 500ms 后出现切片预览并显示每片字符数
- [x] 9.6 实现发布弹窗组件（变更摘要、影响范围、引用数量、回滚目标、自审标记）并接入详情页与编辑器；验证：弹窗五项齐全，自审版本显示标记
- [x] 9.7 实现审核队列页（认领、批注锚定、通过/退回/拒绝、冲突提示）；验证：审核员可认领并按锚点定位到切片
- [x] 9.8 实现检索测试页（查询、过滤器、TopK、命中片段、三路分数与原文定位）；验证：一次检索展示分数与引用路径
- [x] 9.9 实现治理看板页（五类报告 + 下钻）；验证：点击报告项跳转列表并带过滤
- [x] 9.10 前端测试与构建：补页面级校验（权限可见性、错误展示 `code` + `request_id`、懒加载分包）；验证：`cd web && npx tsc --noEmit && npm run build` 通过，构建产物中知识库页面位于独立分包，首屏引用文件 gzip 合计 < 260KB
- [x] 9.11 **闸门 CH3**：跑 H1–H9、I1–I3、J1–J7、K1–K5、L1–L8 全部验收子集；验证：每条有命令与输出证据，任一不过不得进入组 10

## 10. 集成与归档前检查

- [x] 10.1 重新导出契约并校验前端调用：`python scripts/export_openapi.py` 与 `python scripts/check_frontend_contract.py`；验证：`problems=0`，`openapi.json` 与 `openapi.yaml` 已更新且纳入 diff
- [x] 10.2 校验一期兼容白名单：对 6 个一期文件逐个执行 `git diff -U0 -- <file> | grep -E '^-[^-]'`；验证：全部无输出（无删除行）
- [x] 10.3 校验"无提前实现"：`git grep -iE 'langgraph|conversation|tool_call|ontology' -- app/`；验证：仅注释命中或完全无命中
- [x] 10.4 跑全量测试与构建：`python -m pytest -q`、`cd web && npx tsc --noEmit && npm run build`；验证：0 failed，一期 53 项仍在其中，构建成功
- [x] 10.5 三个一致性快照：空库 `create_db --reset --force` → `apply_migrations` → 表数 55 → `gen_models.py` 后 `git diff --exit-code` 为空；验证：三处均无差异
- [x] 10.6 写二期总结（做了什么 / 没做什么 / 已知限制 / 下一步），把一期"前端角色码与后端零重叠"列为已知遗留；验证：文档包含四个小节且已知限制可逐条对应到 design 的 Risks
