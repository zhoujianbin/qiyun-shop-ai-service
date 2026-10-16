# 栖云智家 第一期·企业电商基础平台 交付物清单

定位：可直接开发、联调、上线的第一期（企业电商基础平台）设计包。技术栈：Python 后端（FastAPI + SQLAlchemy 2.0 + Alembic + psycopg3）、React 前端、PostgreSQL 17（含 pgvector）。

## 主文档

| 文件 | 说明 |
|---|---|
| 栖云智家_第一期详细设计.md / .docx | 后端、数据库、API、关键流程、本地环境、非功能、测试、里程碑与后续期次衔接 |
| 栖云智家_第一期_前端详细设计.md / .docx | 前端选型、工程目录、路由总表、逐页规格、组件、API 层、权限、设计令牌、测试与门禁 |

## 契约与数据

| 文件 | 说明 |
|---|---|
| ../栖云智家_第一期_openapi.yaml | OpenAPI 3.1.0：83 条路径、104 个操作、92 个组件 schema，用于生成前端类型与契约测试 |
| schema.sql | PostgreSQL 17 可执行 DDL：shared 13 表、commerce 32 表、knowledge 3 表（预留，本期不写入） |
| seed_all.sql | 开发种子数据：渠道、权限、角色、员工、商品、SKU、库存、客户、订单、支付、物流、售后、退款、发票 |
| verify_phase1.sql | 自检脚本：结构统计、业务一致性、17 项约束负例、端到端流程（事务内回滚）、索引命中 |
| gen_openapi.py / validate_openapi.py | OpenAPI 生成与校验脚本（可复现） |

## 已完成的实测验证

| 验证项 | 结果 |
|---|---|
| DDL 在 PostgreSQL 17.11 执行 | 通过：48 张表、135 索引、75 外键、69 CHECK、35 唯一、21 触发器、3 视图 |
| 种子数据导入 | 通过：7 商品 / 10 SKU / 5 渠道 / 25 权限码 / 7 角色 / 6 员工 / 3 客户 / 4 订单 |
| 约束负例 | 17 项全部 PASS、0 项 FAIL（负库存、金额公式、非法状态、重复运单、重复回调、向量维度等） |
| 端到端流程 | 下单到退款全链路通过，账实一致为真（事务内验证后回滚，不污染演示数据） |
| 支付回调幂等 | 首次回调影响 1 行，重复回调影响 0 行 |
| 索引命中 | 客户订单、后台渠道筛选、中文模糊搜索、向量近邻均命中预期索引 |
| OpenAPI 契约 | PASS：3.1.0，83 路径 / 104 操作 / 92 schema，0 个失效引用，写接口幂等声明齐备 |
| 契约与数据库一致性 | 订单四条状态线与售后状态枚举已对齐 DDL，校验脚本强制检查 |

## 本地数据库

| 项 | 值 |
|---|---|
| 实例 | 本机 PostgreSQL 17.11（容器 ai_customer_service-postgres-1，127.0.0.1:5432） |
| 数据库 | qiyun_shop_dev |
| 进入 | docker exec -it ai_customer_service-postgres-1 psql -U ai_customer_service -d qiyun_shop_dev |
| 重建顺序 | schema.sql 到 seed_all.sql 到 verify_phase1.sql |

口令从容器环境变量读取并写入本地 .env，禁止写入文档或提交仓库。种子账号（admin、ops01、stock01、aftersales01、finance01、cs01、buyer_zhang 等）仅用于开发，上线前必须全部轮换。

## 与后续期次的关系

后续阶段知识库复用 shared 的身份、权限、渠道、附件、审计与幂等；后续阶段 RAG 客服复用订单、物流、售后作为动态事实数据源，并消费 outbox_event；后续阶段本体与工具调用复用同一套权限码、幂等与审计。knowledge schema 与 pgvector 已在一期建好，一期不写入数据。
