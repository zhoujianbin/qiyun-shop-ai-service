# Proposal — 二期：企业知识库平台

## Why

一期只交付了电商底座，企业知识（169 个素材文件：158 篇 Markdown、10 个结构化规则 YAML、1 个校验脚本）仍散落在 `knowledge_raw/` 里，没有任何地方能回答"哪一版是有效的""这条政策是哪个文件定的""改这篇会不会影响别的文档"。一期为此只预留了 `knowledge` schema 的 3 张空表，未写入任何数据。

二期要把这批知识变成**可治理、可发布、可回滚、可追溯**的资产，并交付检索能力与后台管理入口。同时必须为三期（智能客服入口 + RAG + 流式对话）和四期（本体、工具调用、评测）留好接口，但**不提前实现**。

现在做的原因：三期 RAG 的质量天花板由二期决定——切片粒度、引用元数据、规则真源、检索服务化，这四项一旦三期开工就难改；而一期的 `vector(1024)` 与既定模型 `bge-small-zh-v1.5`（512 维）直接冲突，越晚改代价越大。

## What Changes

**数据层（新增为主，不改一期表结构）**
- `knowledge.chunk.embedding` 从 `vector(1024)` 改为 `vector(512)` 并重建 HNSW 索引（当前无数据，改列安全）。
- 一期 3 张预留表共 **9 个加列**（`embedding_status`、`identity_level`、`change_summary` 等），**0 个改约束**。
- 新增 **7 张表**：`knowledge.rule`、`rule_conflict`、`review_task`、`review_comment`、`import_job`、`retrieval_log`、`shared.schema_migration`。库内表数 48 → 55。
- 新增 **12 个 `knowledge:*` 三段式权限码**；收窄 `AUDITOR` 的知识库读权限（避免审计员自动获得全库正文）。

**能力层**
- 导入（MD/TXT/DOCX）+ 结构化规则 YAML 专用通道；sha256 去重、错误清单、幂等键。
- 切片（按标题层级）与本地 `bge-small-zh-v1.5` 异步向量化（worker 支持 `--once`）、重算脚本。
- 文档/版本状态机、发布门禁、回滚、定时生效。
- 结构化规则存储（24 条来自 YAML）、冲突检测（BLOCK/WARN）、BLOCK 阻止发布。
- 审核队列、锚定批注、决定留痕；允许自审但打 `self_review` 标记。
- 混合检索（tsv + trgm + 向量，RRF 融合），**检索能力放在 service 层**供三期直接调用；检索测试页单接口返回 `hits`（稳定引用）与 `debug`（分数）。
- 治理报告（重复/过期/孤立/冲突/与商品表不一致）与概览。
- 后台 7 个页面。
- 发布/归档/回滚/切片完成写 `shared.outbox_event`。

**明确不做**：对话与会话管理、RAG 生成、LangGraph、流式回答、意图识别、转人工、身份核验、本体、工具调用、评测集、规则运行时求值。这些属三/四期；本期只留字段、服务边界与事件出口。

**一期兼容约束**：只允许对 6 个一期文件做"纯追加"（`git diff` 仅 `+` 行），清单与校验方式见 design；不改一期表结构、接口路径/字段、前端类型语义、一期权限码。

**分阶段交付（单 change 内分三组，不拆 sub-change）**

| 组 | 内容 | 阶段闸门（验收子集） |
|---|---|---|
| P2-CH1 基础设施 | 迁移、权限码、embedding 适配器、导入、切片、worker | A5–A7、B1–B7、C2–C9、F1–F8 |
| P2-CH2 治理 | 版本状态机、发布/回滚/定时、门禁、规则与冲突、审核、审计与事件 | D1–D10、E1–E7、G1–G6 |
| P2-CH3 检索与界面 | 混合检索、检索测试、7 个页面、治理报告、运维文档 | H1–H9、I1–I3、J1–J7、K1–K5、L1–L8、A1–A4 全员回归 |

归档前必须跑全量验收（94 条）与 `L8` 的"无提前实现"检查。

## Capabilities

### New Capabilities

- `knowledge-ingestion`: 知识素材进入系统的通道与加工——文档导入（MD/TXT/DOCX）、结构化规则 YAML 导入、front matter 解析、去重与幂等、切片、向量化与重算、导入任务可观测性。
- `knowledge-governance`: 知识从草稿到生效的治理——文档与版本状态机、发布门禁、回滚、定时生效、结构化规则存储与冲突检测、审核与批注、审计留痕、治理报告与概览。
- `knowledge-retrieval`: 检索能力本身——过滤（ACTIVE 版本/有效期/产品/渠道/业务域/身份等级）、全文与向量召回、RRF 融合、阈值、引用结构化、检索日志，且服务层可被进程内直接调用。
- `knowledge-admin-ui`: 后台知识管理界面——概览、文档列表、文档详情、编辑器、审核队列、检索测试、治理看板的页面行为、权限可见性、发布弹窗与切片预览交互。

### Modified Capabilities

（无。一期没有任何 spec；本 change 不修改既有 capability。）

## Impact

**后端**
- 新增：`app/services/knowledge_{import,chunk,embedding,governance,rule,review,retrieval}.py`、`app/api/v1/knowledge*.py`、`app/integrations/embedding.py`、`app/schemas/knowledge.py`。
- 修改（纯追加）：`app/api/v1/router.py`（注册新路由）、`app/integrations/storage.py`（`ALLOWED` 加 `.md`/`.yaml`）、`scripts/bootstrap.py`（收窄 AUDITOR）。
- 新增依赖：`sentence-transformers`、`torch`（CPU）、`numpy`、`python-docx`；首次运行需下载约 95MB 模型（支持离线路径配置）。

**契约**
- 新增 26 条路径 / 32 个操作，全部 `/api/v1/knowledge/*` 扁平风格（与一期一致，无 `/admin` 前缀），全部带 `response_model`。
- 必须重新导出 `openapi.json`/`openapi.yaml` 并通过 `scripts/check_frontend_contract.py`。

**前端**
- 新增 7 个路由与页面、1 个 `react-markdown` 依赖（只做只读预览，不引入编辑器框架）。
- 修改（纯追加）：`web/src/constants/routes.ts`、`web/src/types/permissions.ts`、`web/src/layouts/AdminShell.tsx`（菜单加一组）。

**数据库与运维**
- `db/schema.sql` + `db/migrations/00X_*.sql` + `scripts/apply_migrations.py` + 重跑 `scripts/gen_models.py`（三者必须一致）。
- 新增 `scripts/knowledge_worker.py`、`scripts/reindex_embeddings.py`、`docs/知识库运维.md`。
- 一期 53 项测试保持通过；新增二期测试（真模型只保留 1 条 `slow` smoke）。

**风险**
- 一期 `vector(1024)` 与 512 维模型冲突（方案已定，改列安全）。
- 语料仅约 500 条切片，与需求文档"10 万切片 P95<1.5s"的基准差两个数量级，验收已改为双档。
- 一期末端角色码与后端不重叠（已知遗留，本期不修，记入二期总结）。
- 单 change 合并交付，中途无归档节点；以三组阶段闸门替代。
