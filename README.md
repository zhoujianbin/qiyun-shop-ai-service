# 栖云智家 第一期·企业电商基础平台（可运行实现）

后端 Python（FastAPI + SQLAlchemy 2.0 + psycopg3）+ PostgreSQL 17（pgvector 已启用）+ 前端 React 18（`web/`，Ant Design 5）。
业务范围：商品目录、库存、客户、购物车、订单、支付、履约物流、售后、退款、发票、组织权限、渠道范围、审计、报表。
商品数据取自企业知识库产品主档（`knowledge_raw/01_产品知识`）。不含知识库/RAG/本体/工具调用，仅保留必要的扩展点。

## 快速开始

```bash
cd qiyun-shop
cp .env.example .env                      # 填写本机 PostgreSQL 连接串与 JWT 密钥

python scripts/create_db.py --db qiyun_shop_dev --reset   # 建库 + 应用 45 张表
python scripts/seed.py --orders 60                        # 生成测试数据
python -m uvicorn app.main:app --reload --port 8000       # API + 文档 http://127.0.0.1:8000/docs

cd web && npm install && npm run build && npm run dev     # 前端：dev 代理 /api -> 127.0.0.1:8000
cd .. && python -m pytest -q                             # 45 项测试（含真实 HTTP 端到端）

python scripts/check_frontend_contract.py                 # 前端调用 vs 后端契约一致性
python scripts/export_openapi.py                          # 导出 openapi.json / openapi.yaml
```

前端构建产物存在时，后端会自动挂载 SPA：`/` 与客户端路由返回 index.html，`/assets/*` 返回真实资源，
`/api/*` 未命中仍返回 404（不会被 SPA 吞掉）。

## 如何访问（本地）

启动后端与前端后：

| 入口 | 地址 | 说明 |
|---|---|---|
| 前端（推荐） | http://127.0.0.1:5173 | Vite 开发服务器，已把 /api 代理到 127.0.0.1:8000 |
| API 文档 | http://127.0.0.1:8000/docs | Swagger UI，可直接调试全部接口 |
| 同源版本 | http://127.0.0.1:8000/ | 由后端直接托管 web/dist 构建产物（含客户端路由回退） |

    终端 1（后端）：cd qiyun-shop && python -m uvicorn app.main:app --port 8000
    终端 2（前端）：cd qiyun-shop/web && npm run dev

登录：后台用 admin / ops01 / stock01 / aftersales01 / finance01 / cs01 / auditor01；
客户端用手机号登录（如 13900000001）。统一口令 Qiyun@2026#Dev。

## 测试账号（仅开发环境，上线前必须轮换）

统一初始口令：`Qiyun@2026#Dev`

| 账号 | 角色 | 说明 |
|---|---|---|
| admin | SUPER_ADMIN | 全部权限 |
| ops01 / ops02 | ECOMMERCE_OPS | 商品、类目、订单、履约、报表（渠道范围 1-4 / 1-5） |
| stock01 | INVENTORY_MANAGER | 库存与仓库（渠道范围 1-2，无发货权限） |
| aftersales01 / aftersales02 | AFTER_SALES | 售后、退款、发票 |
| finance01 | FINANCE_VIEWER | 支付、退款、发票、报表只读 |
| cs01 | CS_SUPERVISOR | 订单与售后只读、售后审核 |
| auditor01 | AUDITOR | 全部模块只读 |
| buyer_zhang 等 12 个 | CUSTOMER | `buyer_zhang`、`buyer_li`、`buyer_wang`、`buyer_chen`、`buyer_zhao`、`buyer_sun`、`buyer_zhou`、`buyer_wu`、`buyer_xu`、`buyer_he`、`buyer_guo`、`buyer_ma` |

登录：`POST /api/v1/auth/staff/login`、`POST /api/v1/auth/customer/login`、`POST /api/v1/auth/guest-session`。

## 测试数据概况（seed 结果）

| 类别 | 数量 |
|---|---|
| 渠道账号 | 5（官方商城、天猫、京东、抖音、授权门店） |
| 权限码 / 角色 / 员工 / 客户 | 25 / 7 / 9 / 12 |
| 商品（知识库产品主档） | 7：门锁 L3 Pro、摄像头 C2 守望版、扫地机 R5 Max、吸顶灯 LightOne、网关 Hub G1、AA 电池组、R5 主刷拖布组件 |
| SKU / 仓库 / 承运商 | 8 / 2 / 4 |
| 订单 | 60：待付款 12、已付款 7、已发货 12、已完成 24、退款关闭 5 |
| 售后 / 退款 / 发票 | 14（已完成 5、退货中 4、待审核 5）/ 5（退款 4830.00 元）/ 5 |
| 运行痕迹 | 库存流水 132、审计 313、outbox 271、包裹 41、物流轨迹 82 |

订单由真实服务链路生成：下单锁库存 → 支付 → 发货出库 → 签收 → 售后审核 → 退款，并按随机时间前移，报表呈现真实分布。

## 已实现能力

- **身份权限**：员工/客户/游客登录、旋转刷新令牌、登出、改密吊销会话、PBKDF2 口令、25 权限码 × 7 角色、渠道范围过滤、全量审计。
- **商品目录**：品牌、类目树、SPU、SKU、属性、媒体、上下架、价格变更留痕；C 端公开检索支持关键字/类目/产品线/排序并返回可售数量（pg_trgm 中文模糊匹配）。
- **库存**：仓库、可售/锁定/在途/安全库存、条件更新防超卖、只追加流水（含变动后快照）、预警、乐观锁版本。
- **交易**：购物车、下单锁库存、取消释放、已支付取消需走退款、改地址、备注、状态时间线。
- **支付**：支付单、回调验签与 `event_id` 去重、金额校验、回调幂等、超时关单任务。
- **履约**：发货、**部分发货**、包裹、运单、轨迹去重、签收推进。
- **售后退款**：申请、审核、退货寄回、收货（可回库）、退款执行、UNCERTAIN 人工核查、退款上限校验、需退货必须先收货。
- **发票**：申请、企业抬头税号校验、开具、作废。
- **附件**：上传（扩展名 + MIME + 魔数校验、大小上限、SHA-256 校验和）+ 下载（本人或员工）。
- **报表**：经营看板、销售日汇总、库存报表、售后报表。
- **平台**：统一错误体、`request_id`、`Idempotency-Key` 幂等中间件、分页、结构化日志、outbox 事件（供下游消费）、SPA 静态托管。

## 接口契约

运行时契约：**OpenAPI 3.1.0，89 条路径、112 个操作、140 个组件 schema**（105 个 operation 带具名响应模型），导出为 `openapi.json` / `openapi.yaml`。
前端类型由设计契约 `web/contracts/openapi.yaml` 生成（含完整响应模型）；**路径与方法**由
`scripts/check_frontend_contract.py` 与运行时契约逐条比对（当前 79 个前端调用全部命中）。

约定说明：
- 写接口必须携带 `Idempotency-Key`（`/auth/*`、`/attachments`、`/webhooks/*` 除外），命中回放并返回 `Idempotent-Replay: true`。
- 渠道范围字段以 `channel_account_ids` 为契约字段，`channel_ids` 为兼容别名（二者均被接受并同时返回）。

## 前端契约兼容层

前端字段命名来自设计契约（web/contracts/openapi.yaml），与后端最初实现存在差异。为保证浏览器端可用，
后端在下列位置同时接受/返回两种命名，并由 tests/test_frontend_payloads.py 用前端真实请求体逐项锁定：

| 语义 | 契约字段 | 兼容别名 |
|---|---|---|
| 登录标识 | mobile | username（二选一） |
| 注册 | mobile / nickname / sms_code | phone / display_name |
| 收货人电话 | receiver_mobile / receiver_mobile_masked | receiver_phone |
| 购物车结算 | source_mode + cart_item_ids | items |
| 加购渠道 | channel_account_id（可省略，缺省官方商城） | — |
| 库存调整版本 | expected_version | version |
| 发货承运商 | carrier_code | carrier_id |
| 售后凭证与金额 | evidence_attachment_ids / refund_amount | evidence / expect_amount |
| 售后单关联 | after_sales_id | application_id |
| 退款渠道 | channel | method |
| 审计字段 | before_data / after_data | before / after |
| 员工渠道范围 | channel_account_ids | channel_ids |
| 商品类型筛选 | product_type（SMART_LOCK 等） | product_line（中文产品线） |

**列表响应统一**：`{items, meta:{page,page_size,total}}`。前端所有列表页读 `.items` / `.meta.total`，后端 23 个列表接口已对齐（含 /brands、/warehouses、/carriers、/roles、/permissions、/channel-accounts、/inventory/alerts、/products/{id}/skus、/refunds/{id}/attempts）。**响应模型**：105/112 个 operation 已声明 response_model（未声明的为 system/health、system/version、auth/logout、3 个面向外部厂商的 webhooks 与文件下载）。

## 目录结构

```
qiyun-shop/
├── app/
│   ├── api/v1/       auth、attachment、staff、channel、catalog、inventory、customer、cart、order、payment、
│   │                 fulfillment、aftersales、refund、invoice、report、webhooks
│   ├── core/         配置、数据库、安全、错误、日志、中间件（request_id / 幂等）、分页
│   ├── models/       generated.py 由 db/schema.sql 生成（scripts/gen_models.py）
│   ├── services/     领域服务与状态机（订单、支付、库存、售后、退款、附件、报表等）
│   ├── integrations/ 支付 / 物流 / 存储适配器（本地实现，可替换）
│   └── main.py       应用装配、异常处理、SPA 挂载
├── db/schema.sql     可执行 DDL（shared 13 + commerce 32 + knowledge 3 预留）
├── scripts/          create_db、seed、bootstrap、generate_orders、gen_models、export_openapi、
│                     check_frontend_contract
├── tests/            53 项：鉴权、目录、库存、订单全链路、支付幂等、权限越权、售后退款、附件、
│                     报表、模型一致性、真实 HTTP 端到端、前端契约一致性、前端请求与列表形状回归
├── web/              前端工程（39 页面 / 43 路由 / 24 组件）
│   └── public/       商品 WebP 图片（products/）与首页 Banner（banners/），见「商品图片」
├── docs/             一期设计文档（详细设计、前端详细设计、DDL、种子数据、契约与校验脚本）
├── knowledge_raw/    企业知识库原始文档（169 个 Markdown，按业务域分 16 个目录）
└── LICENSE           MIT
```

## 文档与知识库

### docs/（第一期设计文档）

| 文件 | 内容 |
|---|---|
| 栖云智家_第一期详细设计.md / .docx | 技术选型、架构、45 张表与索引、状态机、接口清单、幂等与权限、风险 |
| 栖云智家_第一期_前端详细设计.md / .docx | 信息架构、43 条路由、页面与组件、状态与错误处理、交互规范 |
| 栖云智家_第一期_openapi.yaml | 第一期接口契约（OpenAPI 3.1） |
| schema.sql | PostgreSQL 17 可执行 DDL（shared 13 + commerce 32 + knowledge 3 预留） |
| seed_all.sql / verify_phase1.sql | 基础数据与校验脚本 |
| gen_openapi.py / validate_openapi.py | 契约生成与校验脚本 |
| README.md | 文档包索引与阅读顺序 |

文档只覆盖第一期范围；后续规划不在本仓库内。

### knowledge_raw/（企业知识库原始文档）

栖云智家企业知识库的原始 Markdown，169 个文件、16 个业务域目录：

    00_企业基础  01_产品知识  02_订单支付与发票  03_物流与履约  04_安装与交付
    05_退换货与退款  06_保修维修与备件  07_账户设备与家庭共享  08_云服务与订阅
    09_客服SOP  10_工单投诉与升级  11_隐私安全与高风险场景  12_场景案例
    13_结构化规则  14_主题手册  99_校验与维护

每篇文档带 `document_id`、`version`、`owner` 等元信息；`SOURCE_OF_TRUTH.md` 定义真源优先级与冲突处理，
`AGENTS.md` / `CLAUDE.md` 定义 AI Agent 的检索与回答规则。商品主档（`01_产品知识/`）是 `scripts/bootstrap.py`
中商品、SKU 与规格参数的来源。
## 商品图片

商品图片放在 `web/public/products/`（Vite 会原样复制到 `dist/products/`，因此 Vite 开发服务器与后端托管两种模式都能直接访问），命名与商品型号一一对应：

| 文件 | 用途 | 尺寸 |
|---|---|---|
| `<型号>.webp` | 商品详情页大图 | 最长边 1000px，WebP q82 |
| `<型号>-thumb.webp` | 列表/首页卡片缩略图 | 最长边 320px，WebP q80 |

商品接口的 `media[].url` 指向大图，`media[].thumb_url` 指向缩略图；前端列表用 `thumb_url`、详情页用 `url`。

压缩结果（7 个商品，原始 PNG 1254×1254 共 10.6MB）：

| 指标 | 原图 | 优化后 |
|---|---|---|
| 单张大小 | 1.16 – 2.52 MB | 8 – 161 KB（大图）、1 – 14 KB（缩略图） |
| 合计 | 10.61 MB | 278 KB + 35 KB |
| 首页 8 张图 | 约 10.4 MB | **35 KB** |

重新生成（需要 Pillow，可用系统 python3 或项目 venv 安装）：

    python scripts/optimize_images.py <原始图片目录>            # 默认输出到 web/public/products
    python scripts/optimize_images.py <原始图片目录> <输出目录>

新增商品图片时：把原始图用上述脚本转换，把 `<型号>.webp` 与 `<型号>-thumb.webp` 放进 `web/public/products/`，
并在 `commerce.product_media.url` 写入 `/products/<型号>.webp`（`scripts/bootstrap.py` 已按此约定生成）。

### 首页 Banner

3 张 Banner 放在 web/public/banners/，命名规则为「名字.webp」（大图 1600px）与「名字-sm.webp」（小图 800px）：

| 文件 | 主题 | 大图 | 小图 |
|---|---|---|---|
| 01-whole-home | 全屋智能（品牌蓝） | 30 KB | 12 KB |
| 02-service | 上门安装与维修（青蓝） | 46 KB | 17 KB |
| 03-accessories | 配件耗材适配（绿） | 54 KB | 16 KB |
| 合计 | 原始 PNG 4.75 MB | 130 KB | 45 KB |

首页轮播用 img 的 srcSet 按视口选择 800w/1600w，第 1 张 eager、其余 lazy；图片本身左侧留白，
页面再叠加对应主色的横向渐变（样式类 qy-banner-scrim）保证标题与按钮可读。

重新生成：

    python scripts/optimize_images.py <Banner 目录> web/public/banners --full-max 1600 --thumb-max 800 --thumb-suffix=-sm --quality 80 --thumb-quality 78
## 验证结果（实测）

| 验证项 | 结果 |
|---|---|
| 后端测试 | `53 passed`（含 8 项前端形状 / 列表形状 / bug 回归测试） |
| 订单全链路 | 下单锁库存 → 支付 → 发货出库 → 签收 → 售后审核 → 退款，状态与流水一致 |
| 真实 HTTP 端到端 | 启动 uvicorn 子进程，按前端调用顺序走完 C 端链路（游客会话 → 公开检索 → 加购 → 我的地址 → 下单 → 支付） |
| SPA 集成 | `/` 与 `/admin/products` 返回 index.html、`/assets/*.js` 返回真实 JS、未知 `/api/*` 保持 404 |
| 前端契约一致性 | 79 个前端调用全部命中运行时契约（0 问题） |
| 运行时响应模型 | schemas 51 增至 140；105 个 operation 带具名响应模型 |
| 前端构建 | tsc --noEmit 0 error；npm run build 成功且无循环 chunk 警告，dist 1.79M（130 个 JS chunk） |
| 首屏打包 | 首屏 gzip 347.6KB 降到 240.5KB（-30.8%），达标 ≤250KB；vendor-antd（626KB）通过深路径导入 + 壳层懒加载 + 人工分包消除 |
| 模型一致性 | 45 张表的列与主键与 DDL 完全一致（防止生成器遗漏列） |
| 幂等 | 同 key 同请求回放、同 key 异指纹 409、重复支付回调不改数据 |
| 权限 | 客户访问后台 403、只读角色写操作 403、渠道范围外订单 403、越权访问他人订单 404 |

开发过程中通过测试与联调发现并修复的真实缺陷：单号秒级碰撞、ORM 缺少 server_default、
售后约束过严、需退货未收货即可退款、模型生成器把 `checksum_sha256` 误判为 CHECK 约束、
SPA 回退吞掉 API 404、前端商品列表调用员工权限接口、前端地址用 user.id 当 customer_id、
前端调整类目缺少 id、员工渠道范围字段命名不一致、2 个后端缺失接口（员工详情、渠道范围查询）、列表响应缺 meta、渠道缺 platform_code 触发 500、已发布商品 PATCH 触发审计 JSON 序列化 500、购物车可售数量只统计单个仓库。

## 已知偏差与后续建议

1. C 端下单渠道：已新增公开接口 GET /api/v1/channels（含 is_default），前端缺省渠道取官方商城；BUY_NOW 仍保留常量兜底。
2. 前端类型仍来自设计契约；运行时契约现已具备响应模型（140 schema），下一步可把前端类型生成切到运行时契约并精简兼容层。
3. 首屏 gzip 240.5KB（react-dom 47.6 + 路由 21.7 + 数据层 32.5 + antd 外壳与主题 138 + CSS 0.9）。再往下压必须动交互：用手写 CSS 导航替换 antd Menu/Dropdown，或去掉 App.useApp() provider，预计还能省 15-30KB。缓存权衡：antd 首屏代码现在入口 chunk 内，antd 升级会击穿入口 hash（react/router/data 仍独立缓存）。
4. 刷新令牌按接口契约放在请求体（设计文档中的 HttpOnly Cookie 方案为后续加固项）。
5. 报表为实时 SQL 聚合，数据量增长后建议引入预聚合表或物化视图。
6. 定时任务（关单、释放预占）尚未接入调度器进程，函数已实现并通过测试（`services/order.close_expired_orders`）。

## 许可证

MIT License，见 [LICENSE](LICENSE)。

