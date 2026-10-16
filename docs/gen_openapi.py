#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成《栖云智家_第一期_openapi.yaml》（OpenAPI 3.1.0）。

只描述栖云智家第一期企业电商基础平台，不引用任何其他仓库或历史系统。
"""
import copy
import os
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "栖云智家_第一期_openapi.yaml")


# --------------------------------------------------------------------------
# 通用小工具：所有 helper 都返回新 dict，避免 YAML 输出锚点/别名
# --------------------------------------------------------------------------
def R(n):
    return {"$ref": "#/components/schemas/" + n}


def PR(n):
    return {"$ref": "#/components/parameters/" + n}


def RS(n):
    return {"$ref": "#/components/responses/" + n}


def O(desc, props, required=None):
    d = {"type": "object", "description": desc, "properties": props}
    if required:
        d["required"] = required
    return d


def A(item, desc=None):
    d = {"type": "array", "items": item if isinstance(item, dict) else R(item)}
    if desc:
        d["description"] = desc
    return d


def S(t, desc=None, **kw):
    d = {"type": t}
    if desc:
        d["description"] = desc
    d.update(kw)
    return d


def E(vals, desc=None, example=None, **kw):
    d = {"type": "string", "enum": list(vals)}
    if desc:
        d["description"] = desc
    if example:
        d["example"] = example
    d.update(kw)
    return d


def money():
    return {
        "type": "string",
        "format": "decimal",
        "pattern": r"^-?\d{1,12}(\.\d{1,2})?$",
        "description": "金额，对应数据库 numeric(14,2)，币种固定 CNY；以字符串传输，禁止使用浮点数。",
        "example": "199.00",
    }


def dt():
    return {"type": "string", "format": "date-time", "description": "RFC 3339 时间（UTC）"}


def dtn():
    return {"type": ["string", "null"], "format": "date-time", "description": "可为空的时间"}


def date():
    return {"type": "string", "format": "date"}


def idf(desc="主键 ID"):
    return {"type": "integer", "format": "int64", "description": desc}


def idn(desc="可为空的外键 ID"):
    return {"type": ["integer", "null"], "format": "int64", "description": desc}


def i32(desc=None, **kw):
    d = {"type": "integer", "format": "int32"}
    if desc:
        d["description"] = desc
    d.update(kw)
    return d


def qty(desc=None):
    return {"type": "integer", "format": "int32", "minimum": 0, "description": desc or "数量"}


def b(desc=None, default=None):
    d = {"type": "boolean"}
    if desc:
        d["description"] = desc
    if default is not None:
        d["default"] = default
    return d


def s(desc=None, **kw):
    d = {"type": "string"}
    if desc:
        d["description"] = desc
    d.update(kw)
    return d


def sn(desc=None):
    return {"type": ["string", "null"], "description": desc or "可为空"}


def currency():
    return {"type": "string", "enum": ["CNY"], "default": "CNY", "description": "币种，第一期固定为 CNY"}


# --------------------------------------------------------------------------
# 枚举（订单与售后四条状态线必须与事实卡完全一致）
# --------------------------------------------------------------------------
ORDER_STATUS = ["CREATED", "PENDING_PAYMENT", "PAID", "FULFILLING", "SHIPPED", "COMPLETED", "CANCELLED", "CLOSED"]
PAYMENT_STATUS = ["UNPAID", "PARTIAL", "PAID", "REFUNDING", "REFUNDED"]
FULFILLMENT_STATUS = ["UNSHIPPED", "PARTIAL_SHIPPED", "SHIPPED", "DELIVERED"]
AFTER_SALES_STATUS = ["NONE", "APPLYING", "PROCESSING", "COMPLETED", "REJECTED"]
AFTER_SALES_APPLICATION_STATUS = ["APPLYING", "PROCESSING", "COMPLETED", "REJECTED"]

ROLE_CODES = ["ENTERPRISE_ADMIN", "ECOM_OPERATOR", "INVENTORY_KEEPER", "AFTER_SALES_SPECIALIST", "FINANCE_AUDITOR", "SERVICE_SUPERVISOR"]
PERMISSION_CODES = [
    "shop:product:read", "shop:product:write",
    "shop:inventory:read", "shop:inventory:write",
    "shop:order:read", "shop:order:write",
    "shop:payment:read",
    "shop:fulfillment:write",
    "shop:aftersales:read", "shop:aftersales:review",
    "shop:invoice:read", "shop:invoice:write",
    "shop:customer:read", "shop:customer:write",
    "shop:channel:read", "shop:channel:write",
    "shop:report:read",
    "shared:staff:read", "shared:staff:write",
    "shared:role:read", "shared:role:write",
    "shared:audit:read",
]
CHANNEL_TYPES = ["OFFICIAL_MALL", "ECOM_FLAGSHIP", "AUTHORIZED_RETAIL"]

# --------------------------------------------------------------------------
# components.schemas
# --------------------------------------------------------------------------
S = {}

S["ApiError"] = O(
    "统一错误响应。所有非 2xx 响应均返回该结构，便于前端与审计统一处理。",
    {
        "code": s("业务错误码，例如 ORDER_INVALID_STATUS", example="ORDER_INVALID_STATUS"),
        "message": s("人类可读的错误说明"),
        "details": {"type": ["object", "null"], "description": "结构化错误详情，例如字段级校验错误或冲突对象", "additionalProperties": True},
        "request_id": s("请求追踪 ID，与响应头 X-Request-Id 及 shared.audit_log.request_id 一致"),
    },
    ["code", "message", "request_id"],
)

S["PageMeta"] = O(
    "统一分页元数据。page 从 1 开始，page_size 取值 1..100；大列表可使用游标分页（cursor + limit），此时返回 next_cursor。",
    {
        "page": {"type": "integer", "minimum": 1, "description": "当前页码，从 1 开始"},
        "page_size": {"type": "integer", "minimum": 1, "maximum": 100, "description": "每页条数，1..100"},
        "total": {"type": "integer", "minimum": 0, "description": "满足条件的记录总数"},
        "has_more": b("是否还有下一页"),
        "next_cursor": sn("游标分页时返回的下一页游标；使用 page/page_size 分页时为 null"),
    },
    ["page", "page_size", "total"],
)

S["TokenPair"] = O(
    "登录/刷新返回的令牌对。access_token 为 JWT，放在 Authorization: Bearer 头。",
    {
        "access_token": s("JWT 访问令牌"),
        "refresh_token": s("刷新令牌（一次性轮换）"),
        "token_type": {"type": "string", "enum": ["Bearer"], "default": "Bearer"},
        "expires_in": i32("访问令牌有效期（秒）"),
        "user": R("CurrentUser"),
    },
    ["access_token", "refresh_token", "token_type", "expires_in"],
)

S["CurrentUser"] = O(
    "当前登录主体（GET /auth/me 或令牌对中返回）。",
    {
        "id": idf(),
        "tenant_id": idf(),
        "party": E(["STAFF", "CUSTOMER", "GUEST"], "主体类型：员工/客户/游客"),
        "username": s("登录名或客户编号"),
        "display_name": s("展示名"),
        "roles": A(E(ROLE_CODES), "员工角色码；客户与游客为空数组"),
        "permissions": A(s(), "权限码集合，例如 shop:order:read"),
        "channel_scope": A(E(CHANNEL_TYPES), "员工可见的渠道范围；管理员为全部渠道"),
    },
    ["id", "party", "display_name"],
)

S["StaffLoginRequest"] = O("员工登录请求。", {
    "username": s("员工登录名"),
    "password": s("登录密码", format="password", minLength=8),
    "otp_code": sn("可选的一次性动态验证码"),
}, ["username", "password"])

S["CustomerLoginRequest"] = O("客户登录请求，支持密码或短信验证码二选一。", {
    "mobile": s("客户手机号", pattern=r"^1[3-9]\d{9}$"),
    "password": sn("登录密码，与 sms_code 二选一"),
    "sms_code": sn("短信验证码，与 password 二选一"),
}, ["mobile"])

S["CustomerRegisterRequest"] = O("客户注册请求。", {
    "mobile": s("客户手机号", pattern=r"^1[3-9]\d{9}$"),
    "password": s("登录密码", format="password", minLength=8),
    "sms_code": s("短信验证码"),
    "nickname": sn("昵称"),
    "channel_account_id": idn(),
}, ["mobile", "password", "sms_code"])

S["GuestSessionRequest"] = O("游客会话请求，用于未注册用户浏览商品与加入购物车。", {
    "channel_account_id": idn(),
    "device_id": sn("设备指纹，用于游客会话合并"),
}, [])

S["RefreshRequest"] = O("刷新令牌请求；refresh_token 一次性轮换。", {
    "refresh_token": s("刷新令牌"),
}, ["refresh_token"])

S["PasswordChangeRequest"] = O("修改当前登录主体密码。", {
    "old_password": s("原密码", format="password"),
    "new_password": s("新密码，需满足企业密码策略", format="password", minLength=8),
}, ["old_password", "new_password"])

S["Role"] = O("角色。", {
    "id": idf(),
    "code": E(ROLE_CODES, "角色码：企业管理员/电商运营/库存仓管/售后专员/财务只读审计/客服主管"),
    "name": s("角色名称"),
    "description": sn("角色说明"),
    "permissions": A(E(PERMISSION_CODES), "该角色拥有的权限码"),
    "is_system": b("是否系统内置角色，内置角色不可删除"),
    "created_at": dt(),
}, ["id", "code", "name", "permissions"])

S["Permission"] = O("权限字典项。", {
    "id": idf(),
    "code": E(PERMISSION_CODES, "权限码，格式 module:resource:action"),
    "name": s("权限名称"),
    "module": s("所属模块，例如 shop 或 shared"),
}, ["id", "code", "name", "module"])

S["StaffUser"] = O("员工用户。", {
    "id": idf(),
    "tenant_id": idf(),
    "username": s("登录名"),
    "display_name": s("姓名"),
    "email": sn("邮箱"),
    "phone_masked": sn("脱敏手机号"),
    "status": E(["ACTIVE", "DISABLED", "LOCKED", "PENDING"], "账号状态"),
    "is_super_admin": b("是否超级管理员"),
    "roles": A(E(ROLE_CODES), "角色码"),
    "channel_scope": A(E(CHANNEL_TYPES), "渠道数据范围"),
    "last_login_at": dtn(),
    "created_at": dt(),
    "updated_at": dt(),
    "version": i32("乐观锁版本号"),
}, ["id", "username", "display_name", "status"])

S["StaffUserCreateRequest"] = O("创建员工请求。", {
    "username": s("登录名", minLength=3, maxLength=64),
    "display_name": s("姓名", maxLength=64),
    "email": sn("邮箱"),
    "phone": sn("手机号"),
    "password": s("初始密码", format="password", minLength=8),
    "role_codes": A(E(ROLE_CODES), "角色码列表"),
    "channel_account_ids": A(idf(), "渠道账号 ID 列表，空表示全渠道"),
}, ["username", "display_name", "password", "role_codes"])

S["StaffUserUpdateRequest"] = O("更新员工请求。仅传入需要修改的字段。", {
    "display_name": s("姓名"),
    "email": sn("邮箱"),
    "phone": sn("手机号"),
    "status": E(["ACTIVE", "DISABLED", "LOCKED", "PENDING"]),
    "version": i32("乐观锁版本号，必须与当前值一致"),
})

S["StaffUserRoles"] = O("员工角色集合。", {
    "user_id": idf(),
    "role_codes": A(E(ROLE_CODES)),
}, ["role_codes"])

S["StaffChannelScopes"] = O("员工渠道数据范围。", {
    "user_id": idf(),
    "channel_account_ids": A(idf(), "渠道账号 ID 列表；空数组表示不限制（仅管理员）"),
}, ["channel_account_ids"])

S["ChannelAccount"] = O(
    "渠道账号。第一期渠道：官方商城、电商官方旗舰店、授权零售门店。",
    {
        "id": idf(),
        "code": s("渠道编码"),
        "name": s("渠道名称"),
        "platform_code": s("平台编码，例如 SELF_MALL / TMALL / JD / OFFLINE"),
        "channel_type": E(CHANNEL_TYPES, "渠道类型"),
        "external_account_id": sn("外部平台店铺或门店标识"),
        "commerce_enabled": b("是否开启交易能力"),
        "status": E(["ACTIVE", "DISABLED"]),
        "created_at": dt(),
        "updated_at": dt(),
    },
    ["id", "code", "name", "channel_type", "status"],
)

S["ChannelAccountCreateRequest"] = O("创建渠道账号请求。", {
    "code": s("渠道编码", maxLength=32),
    "name": s("渠道名称", maxLength=128),
    "platform_code": s("平台编码", maxLength=32),
    "channel_type": E(CHANNEL_TYPES),
    "external_account_id": sn("外部平台店铺或门店标识"),
    "commerce_enabled": b("是否开启交易能力", default=True),
}, ["code", "name", "platform_code", "channel_type"])

S["ChannelAccountUpdateRequest"] = O("更新渠道账号请求。", {
    "name": s("渠道名称"),
    "external_account_id": sn("外部平台店铺或门店标识"),
    "commerce_enabled": b("是否开启交易能力"),
    "status": E(["ACTIVE", "DISABLED"]),
})

S["Brand"] = O("品牌。", {
    "id": idf(),
    "code": s("品牌编码"),
    "name": s("品牌名称"),
    "logo_url": sn("品牌 Logo 地址"),
    "sort_order": i32(),
    "status": E(["ACTIVE", "DISABLED"]),
    "created_at": dt(),
    "updated_at": dt(),
}, ["id", "code", "name", "status"])

S["BrandCreateRequest"] = O("创建品牌请求。", {
    "code": s("品牌编码", maxLength=32),
    "name": s("品牌名称", maxLength=64),
    "logo_url": sn("品牌 Logo 地址"),
    "sort_order": i32(default=0),
}, ["code", "name"])

S["Category"] = O("商品分类。", {
    "id": idf(),
    "parent_id": idn(),
    "code": s("分类编码"),
    "name": s("分类名称"),
    "path": s("祖先路径，例如 /1/12/"),
    "depth": i32("层级，1..5", minimum=1, maximum=5),
    "icon_url": sn("分类图标地址"),
    "sort_order": i32(),
    "status": E(["ACTIVE", "DISABLED"]),
    "children": A(R("Category"), "子分类；分类树接口返回"),
    "created_at": dt(),
    "updated_at": dt(),
}, ["id", "code", "name", "status"])

S["CategoryCreateRequest"] = O("创建分类请求。", {
    "parent_id": idn(),
    "code": s("分类编码", maxLength=48),
    "name": s("分类名称", maxLength=64),
    "icon_url": sn("分类图标地址"),
    "sort_order": i32(default=0),
}, ["code", "name"])

S["CategoryUpdateRequest"] = O("更新分类请求；PATCH /categories 需在请求体携带 id。", {
    "id": idf(),
    "parent_id": idn(),
    "name": s("分类名称"),
    "icon_url": sn("分类图标地址"),
    "sort_order": i32(),
    "status": E(["ACTIVE", "DISABLED"]),
}, ["id"])

S["ProductMedia"] = O("商品媒体（图片、视频、说明书、认证材料）。", {
    "id": idf(),
    "product_id": idf(),
    "sku_id": idn(),
    "media_type": E(["IMAGE", "VIDEO", "MANUAL", "CERT"], "媒体类型"),
    "attachment_id": idn(),
    "url": s("对象存储可访问地址（MinIO 兼容 S3）"),
    "alt_text": sn("替代文本"),
    "is_main": b("是否主图"),
    "sort_order": i32(),
    "created_at": dt(),
}, ["id", "product_id", "media_type", "url"])

S["ProductAttribute"] = O("商品属性/规格。", {
    "id": idf(),
    "product_id": idf(),
    "attribute_id": idf(),
    "code": s("属性编码，例如 power_supply、protocol"),
    "name": s("属性名称，例如 供电方式、无线协议"),
    "data_type": E(["TEXT", "NUMBER", "BOOL", "ENUM", "DATE"]),
    "unit": sn("单位"),
    "value_text": s("属性值"),
    "is_spec": b("是否为销售规格维度"),
    "is_required": b("是否必填"),
    "options": A(s(), "枚举可选值"),
}, ["id", "code", "name", "value_text"])

S["Product"] = O(
    "SPU 商品主档（管理端完整视图）。产品主档字段（规格、供电、协议、防护等级、包装、保修、安装）与销售字段分离。",
    {
        "id": idf(),
        "spu_code": s("SPU 编码"),
        "name": s("商品名称"),
        "subtitle": sn("副标题"),
        "product_line": sn("产品线，例如 智能门锁、家用摄像头、清洁机器人、智能灯具、家庭网关、配件耗材、云服务、安装维修"),
        "model_code": sn("型号编码，例如 QL-L3P"),
        "brand_id": idn(),
        "category_id": idf(),
        "product_type": E(["SMART_LOCK", "CAMERA", "CLEANING_ROBOT", "SMART_LIGHT", "HOME_GATEWAY", "ACCESSORY", "CONSUMABLE", "CLOUD_SERVICE", "INSTALL_SERVICE"]),
        "status": E(["DRAFT", "ON_SALE", "OFF_SHELF", "ARCHIVED"], "商品状态"),
        "description_md": sn("富文本/ Markdown 详情"),
        "highlights": A(s(), "卖点"),
        "spec_summary": {"type": "object", "description": "规格摘要（供电、协议、防护等级、包装清单等）", "additionalProperties": True},
        "warranty_summary": sn("保修摘要"),
        "install_required": b("是否需要上门安装"),
        "install_notes": sn("安装条件说明"),
        "service_scope": sn("服务范围"),
        "currency": currency(),
        "min_price": money(),
        "max_price": money(),
        "channel_scope": A(E(CHANNEL_TYPES), "可售渠道"),
        "media": A(R("ProductMedia")),
        "attributes": A(R("ProductAttribute")),
        "skus": A(R("Sku")),
        "published_at": dtn(),
        "sort_order": i32(),
        "created_at": dt(),
        "updated_at": dt(),
        "version": i32("乐观锁版本号"),
    },
    ["id", "spu_code", "name", "category_id", "status", "currency"],
)

S["ProductCreateRequest"] = O("创建商品（SPU）请求。", {
    "spu_code": s("SPU 编码", maxLength=48),
    "name": s("商品名称", maxLength=160),
    "subtitle": sn("副标题"),
    "brand_id": idn(),
    "category_id": idf(),
    "product_line": sn("产品线"),
    "model_code": sn("型号编码"),
    "product_type": E(["SMART_LOCK", "CAMERA", "CLEANING_ROBOT", "SMART_LIGHT", "HOME_GATEWAY", "ACCESSORY", "CONSUMABLE", "CLOUD_SERVICE", "INSTALL_SERVICE"]),
    "description_md": sn("商品详情"),
    "highlights": A(s()),
    "spec_summary": {"type": "object", "additionalProperties": True},
    "warranty_summary": sn("保修摘要"),
    "install_required": b(),
    "install_notes": sn("安装条件"),
    "service_scope": sn("服务范围"),
    "channel_scope": A(E(CHANNEL_TYPES)),
    "media": A(R("ProductMedia")),
    "attributes": A(R("ProductAttribute")),
    "sort_order": i32(default=0),
}, ["spu_code", "name", "category_id"])

S["ProductUpdateRequest"] = O("更新商品请求。仅传需要修改的字段。", {
    "name": s("商品名称"),
    "subtitle": sn("副标题"),
    "brand_id": idn(),
    "category_id": idf(),
    "product_line": sn("产品线"),
    "model_code": sn("型号编码"),
    "description_md": sn("商品详情"),
    "highlights": A(s()),
    "spec_summary": {"type": "object", "additionalProperties": True},
    "warranty_summary": sn("保修摘要"),
    "install_required": b(),
    "install_notes": sn("安装条件"),
    "service_scope": sn("服务范围"),
    "channel_scope": A(E(CHANNEL_TYPES)),
    "sort_order": i32(),
    "version": i32("乐观锁版本号"),
})

S["ProductPublic"] = O(
    "C 端商品公开详情（已脱敏，仅返回已上架且渠道可见的内容）。",
    {
        "id": idf(),
        "spu_code": s("SPU 编码"),
        "name": s("商品名称"),
        "subtitle": sn("副标题"),
        "category_name": sn("分类名称"),
        "brand_name": sn("品牌名称"),
        "product_type": s("产品类型"),
        "description_md": sn("商品详情"),
        "highlights": A(s()),
        "spec_summary": {"type": "object", "additionalProperties": True},
        "warranty_summary": sn("保修摘要"),
        "install_required": b(),
        "install_notes": sn("安装条件"),
        "service_scope": sn("服务范围"),
        "currency": currency(),
        "min_price": money(),
        "max_price": money(),
        "media": A(R("ProductMedia")),
        "attributes": A(R("ProductAttribute")),
        "skus": A(R("Sku")),
        "published_at": dtn(),
    },
    ["id", "spu_code", "name", "currency"],
)

S["Sku"] = O("SKU 销售单元。", {
    "id": idf(),
    "product_id": idf(),
    "sku_code": s("SKU 编码"),
    "name": s("SKU 名称"),
    "spec_summary": sn("规格摘要，例如 颜色:曜石黑; 版本:标准版"),
    "price": money(),
    "market_price": {"anyOf": [money(), {"type": "null"}], "description": "划线价/市场价"},
    "cost_price": {"anyOf": [money(), {"type": "null"}], "description": "成本价，仅管理端可见"},
    "barcode": sn("条码"),
    "weight_g": {"type": ["integer", "null"], "format": "int32", "description": "重量（克）"},
    "status": E(["ON_SALE", "OFF_SHELF", "ARCHIVED"]),
    "attributes": A(R("ProductAttribute")),
    "sort_order": i32(),
    "created_at": dt(),
    "updated_at": dt(),
    "version": i32("乐观锁版本号"),
}, ["id", "product_id", "sku_code", "name", "price", "status"])

S["SkuCreateRequest"] = O("新增 SKU 请求。", {
    "sku_code": s("SKU 编码", maxLength=64),
    "name": s("SKU 名称", maxLength=160),
    "spec_summary": sn("规格摘要"),
    "price": money(),
    "market_price": sn("市场价"),
    "cost_price": sn("成本价"),
    "barcode": sn("条码"),
    "weight_g": {"type": ["integer", "null"], "format": "int32"},
    "status": E(["ON_SALE", "OFF_SHELF", "ARCHIVED"], default="ON_SALE"),
    "sort_order": i32(default=0),
    "attributes": A(R("ProductAttribute")),
}, ["sku_code", "name", "price"])

S["SkuUpdateRequest"] = O("更新 SKU 请求。", {
    "name": s("SKU 名称"),
    "price": money(),
    "market_price": sn("市场价"),
    "cost_price": sn("成本价"),
    "barcode": sn("条码"),
    "weight_g": {"type": ["integer", "null"], "format": "int32"},
    "status": E(["ON_SALE", "OFF_SHELF", "ARCHIVED"]),
    "sort_order": i32(),
    "version": i32("乐观锁版本号"),
})

S["Warehouse"] = O("仓库。", {
    "id": idf(),
    "code": s("仓库编码"),
    "name": s("仓库名称"),
    "type": E(["SELF", "THIRD_PARTY", "VIRTUAL"], "仓库类型：自营/三方/虚拟"),
    "region": sn("所在区域"),
    "address": sn("地址"),
    "contact_name": sn("联系人"),
    "contact_mobile_masked": sn("脱敏联系电话"),
    "priority": i32("优先级，数值越小越优先"),
    "status": E(["ACTIVE", "DISABLED"]),
    "created_at": dt(),
    "updated_at": dt(),
}, ["id", "code", "name", "status"])

S["WarehouseCreateRequest"] = O("创建仓库请求。", {
    "code": s("仓库编码", maxLength=32),
    "name": s("仓库名称", maxLength=64),
    "type": E(["SELF", "THIRD_PARTY", "VIRTUAL"]),
    "region": sn("所在区域"),
    "address": sn("地址"),
    "contact_name": sn("联系人"),
    "contact_mobile": sn("联系电话"),
    "priority": i32(default=100),
}, ["code", "name"])

S["InventoryItem"] = O(
    "库存结存。可售 qty_available、锁定 qty_reserved、在途 qty_in_transit、安全库存 safety_stock；任何变化必须产生只追加流水。",
    {
        "id": idf(),
        "warehouse_id": idf(),
        "warehouse_name": sn("仓库名称"),
        "sku_id": idf(),
        "sku_code": sn("SKU 编码"),
        "product_name": sn("商品名称"),
        "sku_name": sn("SKU 名称"),
        "qty_available": qty("可售数量"),
        "qty_reserved": qty("锁定数量"),
        "qty_in_transit": qty("在途数量"),
        "safety_stock": qty("安全库存"),
        "is_low_stock": b("可售数量是否低于或等于安全库存"),
        "version": i32("乐观锁版本号，库存调整必须携带"),
        "updated_at": dt(),
    },
    ["id", "warehouse_id", "sku_id", "qty_available", "qty_reserved", "qty_in_transit", "safety_stock"],
)

S["InventoryLedgerEntry"] = O(
    "库存流水（只追加，不允许修改或删除）。change_type 覆盖采购入库、销售出库、锁定、释放、退货入库、调整、报损、调拨。",
    {
        "id": idf(),
        "sku_id": idf(),
        "warehouse_id": idf(),
        "change_type": E(["PURCHASE_IN", "SALE_OUT", "RESERVE", "RELEASE", "RETURN_IN", "ADJUST", "DAMAGE", "TRANSFER_IN", "TRANSFER_OUT"]),
        "qty_delta": i32("变动数量，正数入库/增加，负数出库/减少，不允许为 0"),
        "qty_after": i32("变动后可售结存"),
        "ref_type": sn("关联单据类型，例如 ORDER、AFTER_SALES、PURCHASE"),
        "ref_id": sn("关联单据 ID"),
        "operator_id": idn(),
        "remark": sn("备注"),
        "created_at": dt(),
    },
    ["id", "sku_id", "warehouse_id", "change_type", "qty_delta", "qty_after", "created_at"],
)

S["StockAdjustRequest"] = O("库存调整请求；必须携带 Idempotency-Key，并写入只追加流水。", {
    "warehouse_id": idf(),
    "sku_id": idf(),
    "change_type": E(["ADJUST", "DAMAGE", "PURCHASE_IN", "RETURN_IN", "TRANSFER_IN", "TRANSFER_OUT"], "调整类型"),
    "qty_delta": i32("变动数量，正数增加、负数减少，不允许为 0"),
    "expected_version": i32("期望的库存版本号，用于乐观锁冲突检测"),
    "reason": s("调整原因"),
    "remark": sn("备注"),
}, ["warehouse_id", "sku_id", "change_type", "qty_delta", "expected_version", "reason"])

S["Customer"] = O("客户档案。个人敏感字段脱敏返回。", {
    "id": idf(),
    "user_id": idf(),
    "customer_no": s("客户编号"),
    "nickname": sn("昵称"),
    "real_name": sn("真实姓名（按权限脱敏）"),
    "mobile_masked": sn("脱敏手机号"),
    "email": sn("邮箱"),
    "gender": E(["MALE", "FEMALE", "UNKNOWN"]),
    "default_channel_id": idn(),
    "channel_account_id": idn("首次注册渠道"),
    "tags": A(s(), "客户标签"),
    "total_order_count": i32(),
    "total_paid_amount": money(),
    "last_order_at": dtn(),
    "status": E(["ACTIVE", "DISABLED"]),
    "remark": sn("备注"),
    "created_at": dt(),
    "updated_at": dt(),
}, ["id", "customer_no", "status", "created_at"])

S["CustomerUpdateRequest"] = O("更新客户请求。", {
    "nickname": sn("昵称"),
    "real_name": sn("真实姓名"),
    "gender": E(["MALE", "FEMALE", "UNKNOWN"]),
    "birthday": {"type": ["string", "null"], "format": "date"},
    "tags": A(s()),
    "remark": sn("备注"),
    "default_channel_id": idn(),
})

S["CustomerAddress"] = O("客户收货地址。", {
    "id": idf(),
    "customer_id": idf(),
    "receiver_name": s("收件人"),
    "receiver_mobile_masked": s("脱敏收件手机号"),
    "province": s("省"),
    "city": s("市"),
    "district": s("区/县"),
    "detail": s("详细地址"),
    "postal_code": sn("邮编"),
    "is_default": b("是否默认地址"),
    "status": E(["ACTIVE", "DELETED"]),
    "created_at": dt(),
    "updated_at": dt(),
}, ["id", "customer_id", "receiver_name", "province", "city", "district", "detail"])

S["CustomerAddressRequest"] = O("新增/更新客户地址请求。", {
    "receiver_name": s("收件人", maxLength=64),
    "receiver_mobile": s("收件手机号", pattern=r"^1[3-9]\d{9}$"),
    "province": s("省", maxLength=32),
    "city": s("市", maxLength=32),
    "district": s("区/县", maxLength=32),
    "detail": s("详细地址", maxLength=255),
    "postal_code": sn("邮编"),
    "is_default": b("是否默认地址", default=False),
}, ["receiver_name", "receiver_mobile", "province", "city", "district", "detail"])

S["CartItem"] = O("购物车条目。", {
    "id": idf(),
    "cart_id": idf(),
    "sku_id": idf(),
    "product_id": idf(),
    "product_name": s("商品名称"),
    "sku_name": s("SKU 名称"),
    "image_url": sn("主图地址"),
    "unit_price": money(),
    "quantity": {"type": "integer", "format": "int32", "minimum": 1, "maximum": 999},
    "selected": b("是否勾选结算"),
    "stock_available": b("当前是否可售"),
    "added_at": dt(),
    "updated_at": dt(),
}, ["id", "cart_id", "sku_id", "quantity", "selected"])

S["Cart"] = O("购物车。按客户 + 渠道维度维护。", {
    "id": idf(),
    "customer_id": idf(),
    "channel_account_id": idf(),
    "status": E(["OPEN", "CHECKED_OUT", "ABANDONED"]),
    "items": A(R("CartItem")),
    "item_count": i32("条目数"),
    "selected_quantity": i32("已勾选商品件数"),
    "total_amount": money(),
    "updated_at": dt(),
}, ["id", "customer_id", "status", "items"])

S["CartItemAddRequest"] = O("加入购物车请求。", {
    "sku_id": idf(),
    "quantity": {"type": "integer", "format": "int32", "minimum": 1, "maximum": 999},
    "channel_account_id": idn(),
}, ["sku_id", "quantity"])

S["CartItemUpdateRequest"] = O("更新购物车条目请求。", {
    "quantity": {"type": "integer", "format": "int32", "minimum": 1, "maximum": 999},
    "selected": b(),
})

S["OrderItem"] = O("订单明细行。", {
    "id": idf(),
    "order_id": idf(),
    "product_id": idf(),
    "sku_id": idf(),
    "warehouse_id": idn(),
    "spu_code": s("SPU 编码快照"),
    "sku_code": s("SKU 编码快照"),
    "product_name": s("商品名称快照"),
    "sku_name": s("SKU 名称快照"),
    "spec_summary": sn("规格快照"),
    "image_url": sn("主图快照"),
    "unit_price": money(),
    "quantity": i32("购买数量", minimum=1),
    "goods_amount": money(),
    "discount_amount": money(),
    "payable_amount": money(),
    "refunded_amount": money(),
    "shipped_quantity": i32(),
    "returned_quantity": i32(),
    "item_status": E(["NORMAL", "CANCELLED", "REFUNDED"]),
    "after_sales_status": E(AFTER_SALES_STATUS, "明细售后状态"),
}, ["id", "order_id", "sku_id", "quantity", "payable_amount"])

S["OrderTimelineEntry"] = O("订单状态时间线（来自 order_status_history）。", {
    "id": idf(),
    "order_id": idf(),
    "field": E(["status", "payment_status", "fulfillment_status", "after_sales_status"], "变更的状态线"),
    "from_value": sn("变更前值"),
    "to_value": s("变更后值"),
    "reason": sn("变更原因"),
    "operator_type": E(["STAFF", "CUSTOMER", "SYSTEM", "GUEST"]),
    "operator_id": idn(),
    "created_at": dt(),
}, ["id", "order_id", "field", "to_value", "created_at"])

S["Order"] = O(
    "订单主表。业务状态、支付状态、履约状态、售后状态四条状态线相互独立；枚举与第一期状态机完全一致。",
    {
        "id": idf(),
        "order_no": s("订单号"),
        "channel_account_id": idf(),
        "customer_id": idf(),
        "source": E(["OFFICIAL_MALL", "ECOMMERCE", "RETAIL", "MANUAL"], "订单来源渠道"),
        "external_order_no": sn("外部平台订单号"),
        "currency": currency(),
        "goods_amount": money(),
        "discount_amount": money(),
        "shipping_amount": money(),
        "payable_amount": money(),
        "paid_amount": money(),
        "refunded_amount": money(),
        "status": E(ORDER_STATUS, "订单业务状态"),
        "payment_status": E(PAYMENT_STATUS, "支付状态"),
        "fulfillment_status": E(FULFILLMENT_STATUS, "履约状态"),
        "after_sales_status": E(AFTER_SALES_STATUS, "售后状态"),
        "receiver_name": s("收件人快照"),
        "receiver_phone_masked": s("脱敏收件手机号快照"),
        "shipping_address": {"type": "object", "description": "收货地址快照", "additionalProperties": True},
        "address_id": idn(),
        "buyer_remark": sn("买家备注"),
        "staff_remark": sn("商家备注"),
        "pay_deadline": dtn(),
        "paid_at": dtn(),
        "shipped_at": dtn(),
        "completed_at": dtn(),
        "cancelled_at": dtn(),
        "cancel_reason": sn("取消原因"),
        "closed_at": dtn(),
        "items": A(R("OrderItem")),
        "created_at": dt(),
        "updated_at": dt(),
        "version": i32("乐观锁版本号"),
    },
    ["id", "order_no", "channel_account_id", "customer_id", "status", "payment_status", "fulfillment_status", "after_sales_status", "currency", "payable_amount"],
)

S["OrderItemInput"] = O("创建订单时的商品行输入。", {
    "sku_id": idf(),
    "quantity": {"type": "integer", "format": "int32", "minimum": 1, "maximum": 999},
}, ["sku_id", "quantity"])

S["CreateOrderRequest"] = O("创建订单请求。支持购物车结算或立即购买；下单即锁定库存。", {
    "channel_account_id": idf(),
    "source": E(["OFFICIAL_MALL", "ECOMMERCE", "RETAIL", "MANUAL"]),
    "source_mode": E(["CART", "BUY_NOW"], "结算来源"),
    "cart_item_ids": A(idf(), "购物车条目 ID；source_mode=CART 时使用"),
    "items": A(R("OrderItemInput"), "直接购买商品行；source_mode=BUY_NOW 时使用"),
    "address_id": idf("收货地址 ID"),
    "buyer_remark": sn("买家备注"),
    "coupon_code": sn("优惠券码"),
    "expected_delivery_time": dtn(),
}, ["channel_account_id", "source_mode", "address_id"])

S["OrderCancelRequest"] = O("取消订单请求。", {
    "reason": s("取消原因"),
    "notify_customer": b("是否通知客户", default=True),
}, ["reason"])

S["OrderAddressUpdateRequest"] = O("修改订单收货地址请求（仅未发货或按策略允许时）。", {
    "address_id": idn(),
    "receiver_name": s("收件人"),
    "receiver_mobile": s("收件手机号", pattern=r"^1[3-9]\d{9}$"),
    "province": s("省"),
    "city": s("市"),
    "district": s("区/县"),
    "detail": s("详细地址"),
})

S["OrderRemarkUpdateRequest"] = O("修改订单备注请求。", {
    "buyer_remark": sn("买家备注"),
    "staff_remark": sn("商家备注"),
})

S["ShipmentItem"] = O("包裹明细。", {
    "id": idf(),
    "shipment_id": idf(),
    "order_item_id": idf(),
    "sku_id": idf(),
    "product_name": sn("商品名称快照"),
    "sku_name": sn("SKU 名称快照"),
    "quantity": {"type": "integer", "format": "int32", "minimum": 1},
}, ["id", "shipment_id", "order_item_id", "quantity"])

S["TrackingEvent"] = O("物流轨迹事件。", {
    "id": idf(),
    "shipment_id": idf(),
    "event_time": dt(),
    "status": s("承运商状态码/描述"),
    "description": s("轨迹描述"),
    "location": sn("发生地"),
    "source": E(["CARRIER_WEBHOOK", "MANUAL", "API"], "轨迹来源"),
    "raw": {"type": ["object", "null"], "description": "承运商原始报文", "additionalProperties": True},
    "created_at": dt(),
}, ["id", "shipment_id", "event_time", "status", "description"])

S["Carrier"] = O("承运商。", {
    "id": idf(),
    "code": s("承运商编码，例如 SF、JD、YTO"),
    "name": s("承运商名称"),
    "tracking_url_template": sn("查询链接模板，含 {tracking_no} 占位符"),
    "status": E(["ACTIVE", "DISABLED"]),
}, ["id", "code", "name", "status"])

S["Shipment"] = O("包裹/运单，支持部分发货与多包裹。", {
    "id": idf(),
    "shipment_no": s("包裹号"),
    "order_id": idf(),
    "warehouse_id": idn(),
    "carrier_id": idf(),
    "carrier_code": s("承运商编码"),
    "carrier_name": sn("承运商名称"),
    "tracking_no": s("运单号"),
    "status": E(["PENDING", "PICKED_UP", "IN_TRANSIT", "DELIVERED", "EXCEPTION", "RETURNED"], "包裹状态"),
    "package_count": i32("包裹件数", minimum=1),
    "receiver_name": s("收件人"),
    "receiver_phone_masked": s("脱敏收件手机号"),
    "address_text": s("地址文本快照"),
    "shipped_at": dtn(),
    "delivered_at": dtn(),
    "exception_note": sn("异常说明，例如拒收、破损"),
    "items": A(R("ShipmentItem")),
    "tracking_events": A(R("TrackingEvent")),
    "created_at": dt(),
    "updated_at": dt(),
}, ["id", "shipment_no", "order_id", "carrier_id", "tracking_no", "status"])

S["ShipRequest"] = O("订单发货请求；支持一次或多次部分发货。", {
    "warehouse_id": idf(),
    "carrier_code": s("承运商编码"),
    "tracking_no": s("运单号"),
    "package_count": i32("包裹件数", minimum=1, default=1),
    "shipped_at": dtn(),
    "items": A(R("ShipmentItem"), "本次发货的订单明细行与数量"),
    "remark": sn("备注"),
}, ["warehouse_id", "carrier_code", "tracking_no", "items"])

S["TrackingEventCreateRequest"] = O("人工登记物流轨迹请求。", {
    "event_time": dt(),
    "status": s("状态码/描述"),
    "description": s("轨迹描述"),
    "location": sn("发生地"),
}, ["event_time", "status", "description"])

S["Payment"] = O(
    "支付单。不存储完整支付敏感信息；订单的支付进度见 Order.payment_status。",
    {
        "id": idf(),
        "payment_no": s("支付单号"),
        "order_id": idf(),
        "method": E(["MOCK", "WECHAT_PAY", "ALIPAY", "UNIONPAY", "BALANCE"], "支付方式"),
        "amount": money(),
        "currency": currency(),
        "status": E(["PENDING", "SUCCESS", "FAILED", "CLOSED"], "支付单状态"),
        "channel_txn_no": sn("渠道交易号"),
        "pay_url": sn("收银台跳转地址"),
        "expires_at": dtn(),
        "paid_at": dtn(),
        "closed_at": dtn(),
        "failure_code": sn("失败错误码"),
        "failure_message": sn("失败原因"),
        "created_at": dt(),
        "updated_at": dt(),
        "version": i32(),
    },
    ["id", "payment_no", "order_id", "method", "amount", "currency", "status"],
)

S["PaymentCreateRequest"] = O("创建支付单请求。", {
    "order_id": idf(),
    "method": E(["MOCK", "WECHAT_PAY", "ALIPAY", "UNIONPAY", "BALANCE"]),
    "return_url": sn("同步跳回地址"),
    "client_ip": sn("客户端 IP，用于风控"),
}, ["order_id", "method"])

S["MockPaymentSucceedRequest"] = O("模拟支付成功（仅 MOCK 渠道与开发/测试环境可用）。", {
    "channel_txn_no": sn("模拟渠道交易号"),
    "paid_at": dtn(),
    "remark": sn("备注"),
})

S["PaymentCallback"] = O(
    "支付渠道回调报文与入库记录。同 event_id 只处理一次，签名校验后落 payment_callback_log。",
    {
        "id": idf(),
        "method": E(["MOCK", "WECHAT_PAY", "ALIPAY", "UNIONPAY", "BALANCE"]),
        "event_id": s("渠道事件 ID，用于去重"),
        "payment_no": sn("本地支付单号"),
        "channel_txn_no": sn("渠道交易号"),
        "order_no": sn("订单号"),
        "amount": money(),
        "currency": currency(),
        "status": s("渠道结果状态"),
        "signature_valid": b("回调签名是否校验通过"),
        "processed": b("是否已成功处理"),
        "process_result": sn("处理结果说明"),
        "payload": {"type": "object", "description": "渠道原始报文", "additionalProperties": True},
        "created_at": dt(),
    },
    ["event_id", "method", "amount", "payload"],
)

S["AfterSalesMessage"] = O("售后沟通消息。", {
    "id": idf(),
    "application_id": idf(),
    "sender_type": E(["CUSTOMER", "STAFF", "SYSTEM"]),
    "sender_id": idn(),
    "content": s("消息内容"),
    "attachment_ids": A(idf(), "附件 ID"),
    "created_at": dt(),
}, ["id", "application_id", "sender_type", "content", "created_at"])

S["AfterSalesApplication"] = O(
    "售后申请。覆盖退款、退货退款、维修、换货、安装、保修；status 与第一期售后状态机一致。",
    {
        "id": idf(),
        "application_no": s("售后单号"),
        "order_id": idf(),
        "order_no": sn("订单号"),
        "order_item_id": idn(),
        "customer_id": idf(),
        "type": E(["REFUND_ONLY", "RETURN_REFUND", "REPAIR", "REPLACEMENT", "INSTALLATION", "WARRANTY"], "售后类型"),
        "status": E(AFTER_SALES_APPLICATION_STATUS, "售后状态"),
        "reason_code": s("原因码"),
        "description": sn("问题描述"),
        "evidence_attachment_ids": A(idf(), "凭证附件 ID"),
        "quantity": i32("售后数量", minimum=1),
        "refund_amount": money(),
        "return_carrier_code": sn("退货承运商编码"),
        "return_tracking_no": sn("退货运单号"),
        "applied_at": dt(),
        "reviewed_at": dtn(),
        "reviewer_id": idn(),
        "review_remark": sn("审核意见"),
        "received_at": dtn(),
        "completed_at": dtn(),
        "cancel_reason": sn("取消原因"),
        "messages": A(R("AfterSalesMessage")),
        "created_at": dt(),
        "updated_at": dt(),
        "version": i32(),
    },
    ["id", "application_no", "order_id", "customer_id", "type", "status", "applied_at"],
)

S["AfterSalesCreateRequest"] = O("提交售后申请请求。", {
    "order_id": idf(),
    "order_item_id": idn(),
    "type": E(["REFUND_ONLY", "RETURN_REFUND", "REPAIR", "REPLACEMENT", "INSTALLATION", "WARRANTY"]),
    "reason_code": s("原因码"),
    "description": sn("问题描述"),
    "evidence_attachment_ids": A(idf(), "凭证附件 ID"),
    "quantity": {"type": "integer", "format": "int32", "minimum": 1, "default": 1},
    "refund_amount": sn("期望退款金额（仅退款/退货退款）"),
}, ["order_id", "type", "reason_code"])

S["ReviewRequest"] = O("售后审核请求。", {
    "decision": E(["APPROVE", "REJECT"], "审核结论"),
    "approved_amount": sn("批准的退款金额"),
    "reason": sn("审核说明/驳回原因"),
    "remark": sn("内部备注"),
    "need_return": b("是否需要客户寄回"),
    "return_address": sn("退货地址"),
    "assignee_id": idn("处理人"),
}, ["decision"])

S["ReturnShipmentRequest"] = O("客户寄回退货包裹请求。", {
    "carrier_code": s("承运商编码"),
    "tracking_no": s("退货运单号"),
    "shipped_at": dtn(),
    "remark": sn("备注"),
}, ["carrier_code", "tracking_no"])

S["AfterSalesReceiveRequest"] = O("仓库确认收到退货请求。", {
    "received": b("是否收到且验收通过", default=True),
    "warehouse_id": idn(),
    "remark": sn("验收说明"),
})

S["AfterSalesCompleteRequest"] = O("完成售后请求（触发退款/换货/维修结案）。", {
    "conclusion": s("结案结论"),
    "refund_amount": sn("实际退款金额"),
    "remark": sn("备注"),
}, ["conclusion"])

S["AfterSalesCancelRequest"] = O("取消售后申请请求。", {
    "reason": s("取消原因"),
}, ["reason"])

S["AfterSalesMessageCreateRequest"] = O("新增售后沟通消息请求。", {
    "content": s("消息内容", maxLength=2000),
    "attachment_ids": A(idf(), "附件 ID"),
    "visible_to_customer": b("是否对客户可见", default=True),
}, ["content"])

S["Refund"] = O("退款单。退款执行需幂等，并记录每次渠道尝试。", {
    "id": idf(),
    "refund_no": s("退款单号"),
    "order_id": idf(),
    "payment_id": idn(),
    "after_sales_id": idn(),
    "customer_id": idf(),
    "amount": money(),
    "currency": currency(),
    "reason": sn("退款原因"),
    "status": E(["PENDING", "PROCESSING", "SUCCESS", "FAILED", "CANCELLED"], "退款状态"),
    "channel": s("退款渠道"),
    "requested_by": idn(),
    "executed_at": dtn(),
    "attempts": A(R("RefundAttempt")),
    "created_at": dt(),
    "updated_at": dt(),
    "version": i32(),
}, ["id", "refund_no", "order_id", "customer_id", "amount", "currency", "status"])

S["RefundCreateRequest"] = O("发起退款请求。", {
    "order_id": idf(),
    "after_sales_id": idn(),
    "order_item_id": idn(),
    "amount": sn("退款金额"),
    "reason": s("退款原因"),
    "channel": sn("退款渠道，默认原路退回"),
}, ["order_id", "reason"])

S["RefundAttempt"] = O("退款执行尝试记录。", {
    "id": idf(),
    "refund_id": idf(),
    "attempt_no": i32("第几次尝试", minimum=1),
    "channel": s("渠道"),
    "status": E(["PENDING", "PROCESSING", "SUCCESS", "FAILED"]),
    "request_payload": {"type": ["object", "null"], "additionalProperties": True},
    "response_payload": {"type": ["object", "null"], "additionalProperties": True},
    "error_code": sn(),
    "error_message": sn(),
    "attempted_at": dt(),
}, ["id", "refund_id", "attempt_no", "status", "attempted_at"])

S["Invoice"] = O("发票申请与开具记录。", {
    "id": idf(),
    "invoice_no": sn("发票号码；未开具时为空"),
    "order_id": idf(),
    "customer_id": idf(),
    "type": E(["VAT_NORMAL", "VAT_SPECIAL", "ELECTRONIC"], "发票类型"),
    "title": s("发票抬头"),
    "tax_no": sn("纳税人识别号"),
    "bank_name": sn("开户行"),
    "bank_account_masked": sn("脱敏银行账号"),
    "registered_address": sn("注册地址"),
    "registered_phone_masked": sn("脱敏注册电话"),
    "amount": money(),
    "tax_amount": money(),
    "status": E(["DRAFT", "PENDING", "ISSUED", "VOID"], "发票状态"),
    "issue_type": E(["BLUE", "RED"], "蓝票/红冲票"),
    "email": sn("接收邮箱"),
    "issued_at": dtn(),
    "attachment_id": idn("电子发票文件附件 ID"),
    "remark": sn("备注"),
    "created_at": dt(),
    "updated_at": dt(),
}, ["id", "order_id", "customer_id", "type", "title", "status", "amount"])

S["InvoiceCreateRequest"] = O("申请开票请求。", {
    "order_id": idf(),
    "type": E(["VAT_NORMAL", "VAT_SPECIAL", "ELECTRONIC"]),
    "title": s("发票抬头"),
    "tax_no": sn("纳税人识别号；专票必填"),
    "bank_name": sn("开户行"),
    "bank_account": sn("银行账号"),
    "registered_address": sn("注册地址"),
    "registered_phone": sn("注册电话"),
    "email": sn("接收邮箱"),
    "remark": sn("备注"),
}, ["order_id", "type", "title"])

S["InvoiceIssueRequest"] = O("开具发票请求。", {
    "invoice_no": s("发票号码"),
    "issue_type": E(["BLUE", "RED"], default="BLUE"),
    "tax_amount": sn("税额"),
    "attachment_id": idn("电子发票文件附件 ID"),
    "issued_at": dtn(),
}, ["invoice_no"])

S["InvoiceVoidRequest"] = O("作废/红冲发票请求。", {
    "reason": s("作废原因"),
    "issue_type": E(["RED"], "红冲时固定为 RED"),
}, ["reason"])

S["AuditLog"] = O("审计日志（只追加）。记录操作者、对象、前后值与 request_id。", {
    "id": idf(),
    "tenant_id": idf(),
    "actor_type": E(["STAFF", "CUSTOMER", "GUEST", "SYSTEM"]),
    "actor_id": idn(),
    "actor_label": sn("操作者展示名"),
    "action": s("动作，例如 order.cancel"),
    "resource_type": s("资源类型，例如 Order"),
    "resource_id": sn("资源 ID"),
    "channel_account_id": idn(),
    "before_data": {"type": ["object", "null"], "description": "变更前值", "additionalProperties": True},
    "after_data": {"type": ["object", "null"], "description": "变更后值", "additionalProperties": True},
    "request_id": sn("请求追踪 ID"),
    "ip": sn("来源 IP"),
    "user_agent": sn("User-Agent"),
    "created_at": dt(),
}, ["id", "actor_type", "action", "resource_type", "created_at"])

S["Attachment"] = O("附件（对象存储 MinIO 兼容 S3）。", {
    "id": idf(),
    "owner_type": s("归属资源类型，例如 Product、AfterSalesApplication"),
    "owner_id": sn("归属资源 ID"),
    "file_name": s("文件名"),
    "content_type": s("MIME 类型"),
    "size_bytes": {"type": "integer", "format": "int64", "minimum": 1, "maximum": 20971520, "description": "文件大小（字节），单文件不超过 20 MiB"},
    "storage_key": s("对象存储 key"),
    "url": s("访问地址"),
    "checksum_sha256": s("SHA-256 校验和"),
    "uploaded_by": idn(),
    "is_public": b("是否公开可读"),
    "status": E(["PENDING", "READY", "REJECTED", "DELETED"]),
    "created_at": dt(),
}, ["id", "file_name", "content_type", "size_bytes", "url", "status"])

S["DashboardReport"] = O("经营看板报表。", {
    "generated_at": dt(),
    "date_from": date(),
    "date_to": date(),
    "channel_account_id": idn(),
    "gross_sales_amount": money(),
    "net_sales_amount": money(),
    "discount_amount": money(),
    "refund_amount": money(),
    "order_count": i32(),
    "paid_order_count": i32(),
    "avg_order_value": money(),
    "new_customers": i32(),
    "low_stock_count": i32(),
    "pending_after_sales_count": i32(),
    "conversion_rate": {"type": "number", "format": "double", "description": "支付订单数/下单数，仅比率使用浮点"},
    "channel_breakdown": A(O("渠道维度汇总", {"channel_account_id": idf(), "channel_name": s(), "order_count": i32(), "sales_amount": money()})),
    "top_products": A(O("热销商品", {"product_id": idf(), "product_name": s(), "quantity": i32(), "sales_amount": money()})),
}, ["generated_at", "gross_sales_amount", "order_count"])

S["SalesDailyReport"] = O("销售日报行。", {
    "date": date(),
    "channel_account_id": idn(),
    "order_count": i32(),
    "paid_order_count": i32(),
    "gmv": money(),
    "net_sales_amount": money(),
    "refund_amount": money(),
    "new_customers": i32(),
    "channel_breakdown": A(O("渠道维度汇总", {"channel_account_id": idf(), "order_count": i32(), "sales_amount": money()})),
    "top_skus": A(O("热销 SKU", {"sku_id": idf(), "sku_name": s(), "quantity": i32(), "sales_amount": money()})),
}, ["date", "gmv", "order_count"])

S["InventoryReport"] = O("库存报表。", {
    "generated_at": dt(),
    "warehouse_count": i32(),
    "sku_count": i32(),
    "total_available_qty": qty(),
    "total_reserved_qty": qty(),
    "total_in_transit_qty": qty(),
    "low_stock_count": i32(),
    "out_of_stock_count": i32(),
    "by_warehouse": A(O("仓库维度库存", {"warehouse_id": idf(), "warehouse_name": s(), "available_qty": qty(), "reserved_qty": qty(), "in_transit_qty": qty(), "low_stock_count": i32()})),
}, ["generated_at", "total_available_qty"])

S["AfterSalesReport"] = O("售后报表。", {
    "generated_at": dt(),
    "date_from": date(),
    "date_to": date(),
    "application_count": i32(),
    "completed_count": i32(),
    "rejected_count": i32(),
    "avg_processing_hours": {"type": "number", "format": "double", "description": "平均处理时长（小时）"},
    "refund_amount": money(),
    "by_type": A(O("售后类型维度", {"type": s(), "count": i32()})),
    "by_status": A(O("售后状态维度", {"status": E(AFTER_SALES_STATUS), "count": i32()})),
}, ["generated_at", "application_count"])

S["SystemHealth"] = O("系统健康检查。", {
    "status": E(["UP", "DEGRADED", "DOWN"]),
    "time": dt(),
    "version": s("服务版本"),
    "checks": A(O("依赖检查项", {"name": s("例如 postgres、redis、object_storage"), "status": E(["UP", "DEGRADED", "DOWN"]), "latency_ms": {"type": "number", "format": "double"}, "message": sn()})),
}, ["status", "time"])

S["VersionInfo"] = O("版本信息。", {
    "name": s("服务名称"),
    "version": s("应用版本"),
    "api_version": s("API 版本，例如 v1"),
    "python_version": s("运行时版本"),
    "environment": s("运行环境，例如 dev/test/prod"),
    "build_time": dtn(),
    "git_commit": sn("构建提交号"),
}, ["name", "version", "api_version"])

S["WebhookAck"] = O("Webhook 统一应答，避免渠道重复推送。", {
    "received": b("是否已接收"),
    "event_id": sn("事件 ID"),
    "duplicate": b("是否为重复事件"),
    "processed": b("是否已处理完成"),
    "message": sn("处理说明"),
}, ["received"])

S["LogisticsCallback"] = O("物流承运商回调报文。", {
    "carrier": s("承运商编码"),
    "tracking_no": s("运单号"),
    "event_time": dt(),
    "status": s("状态码/描述"),
    "description": s("轨迹描述"),
    "location": sn("发生地"),
    "raw": {"type": ["object", "null"], "additionalProperties": True},
}, ["carrier", "tracking_no", "event_time", "status", "description"])

S["RefundCallback"] = O("退款渠道回调报文。", {
    "refund_no": s("本地退款单号"),
    "channel": s("退款渠道"),
    "channel_refund_no": sn("渠道退款单号"),
    "status": s("渠道退款状态"),
    "amount": money(),
    "currency": currency(),
    "raw": {"type": ["object", "null"], "additionalProperties": True},
}, ["refund_no", "channel", "status", "amount"])


# --------------------------------------------------------------------------
# components：parameters / responses / securitySchemes
# --------------------------------------------------------------------------
PARAMS = {
    "Page": {
        "name": "page", "in": "query", "required": False,
        "description": "页码，从 1 开始；与 page_size 配合使用标准分页。",
        "schema": {"type": "integer", "minimum": 1, "default": 1},
    },
    "PageSize": {
        "name": "page_size", "in": "query", "required": False,
        "description": "每页条数，取值 1..100，默认 20。",
        "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
    },
    "Cursor": {
        "name": "cursor", "in": "query", "required": False,
        "description": "游标分页游标；用于审计日志、库存流水、订单时间线等大列表，避免深分页。首次请求不传，后续使用 meta.next_cursor。",
        "schema": {"type": ["string", "null"]},
    },
    "Limit": {
        "name": "limit", "in": "query", "required": False,
        "description": "游标分页单次返回条数，取值 1..100，默认 20。",
        "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
    },
    "IdempotencyKey": {
        "name": "Idempotency-Key", "in": "header", "required": True,
        "description": "写接口必填幂等键。相同 key 且相同请求指纹会回放首次结果；相同 key 但指纹不同返回 409。写入 shared.idempotency_record，有效 24 小时。",
        "schema": {"type": "string", "minLength": 8, "maxLength": 128},
    },
}

RESPONSES = {
    "BadRequest": ("400 请求参数或业务校验失败", "BadRequest"),
    "Unauthorized": ("401 未认证或令牌过期", "Unauthorized"),
    "Forbidden": ("403 已认证但无权限或超出渠道数据范围", "Forbidden"),
    "NotFound": ("404 资源不存在或不可见", "NotFound"),
    "Conflict": ("409 状态冲突、唯一键冲突或幂等键指纹冲突", "Conflict"),
    "UnprocessableEntity": ("422 请求体字段校验失败", "UnprocessableEntity"),
    "TooManyRequests": ("429 触发限流", "TooManyRequests"),
    "InternalServerError": ("500 服务器内部错误", "InternalServerError"),
}
RESPS = {}
for _k, (_desc, _ex) in RESPONSES.items():
    RESPS[_k] = {
        "description": _desc,
        "content": {"application/json": {"schema": R("ApiError"), "example": {"code": _ex.upper(), "message": _desc, "request_id": "req_01HZYQ0000000000000000000"}}},
    }

SECURITY_SCHEMES = {
    "bearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "JWT 访问令牌。除 /auth/* 的登录/注册/游客/刷新与 /webhooks/* 外，所有接口默认需要 Authorization: Bearer <token>。",
    }
}


# --------------------------------------------------------------------------
# paths 构建器
# --------------------------------------------------------------------------
TAGS = [
    ("认证与身份", "员工、客户、游客登录注册、令牌与密码"),
    ("组织与权限", "员工、角色、权限与渠道数据范围"),
    ("渠道账号", "官方商城、电商官方旗舰店、授权零售门店"),
    ("商品中心", "品牌、分类、SPU/SKU、上下架与公开详情"),
    ("附件", "对象存储附件上传与查询"),
    ("库存中心", "仓库、结存、调整与只追加流水"),
    ("客户中心", "客户档案、地址与客户订单"),
    ("购物车", "购物车与条目"),
    ("订单中心", "下单、查询、取消、改址、备注、时间线与发货"),
    ("支付中心", "支付单、模拟支付与渠道回调"),
    ("履约与物流", "承运商、包裹、轨迹与物流回调"),
    ("售后中心", "售后申请、审核、寄回、收货、完成与沟通"),
    ("退款", "退款单、执行、尝试记录与回调"),
    ("发票", "开票申请、开具与作废/红冲"),
    ("报表", "经营看板、销售、库存与售后报表"),
    ("审计与系统", "审计日志、健康检查与版本信息"),
]
T_AUTH, T_STAFF, T_CHANNEL, T_CATALOG, T_ATTACH, T_INV, T_CUST, T_CART, T_ORDER, T_PAY, T_FUL, T_AS, T_REFUND, T_INVOICE, T_REPORT, T_SYS = [t[0] for t in TAGS]

PATHS = {}
_ERROR_CODE_BY_NAME = {
    "400": "BadRequest",
    "401": "Unauthorized",
    "403": "Forbidden",
    "404": "NotFound",
    "409": "Conflict",
    "422": "UnprocessableEntity",
    "429": "TooManyRequests",
    "500": "InternalServerError",
}
_error_responses = list(_ERROR_CODE_BY_NAME.items())


def _oid(method, path):
    return method + "_" + path.strip("/").replace("/", "_").replace("{", "").replace("}", "").replace("-", "_")


def add(path, method, tag, summary, *, desc=None, params=None, query=None, body=None, body_ct="application/json",
        body_required=True, ok=200, ok_desc=None, schema=None, list_of=None, public=False, security=None,
        idem=None, headers=None):
    method = method.lower()
    assert path.startswith("/"), path
    item = PATHS.setdefault(path, {})
    assert method not in item, "duplicate %s %s" % (method, path)

    is_webhook = path.startswith("/webhooks/")
    is_login = path.endswith("/login")
    is_upload = path == "/attachments" and method == "post"
    if idem is None:
        idem = method in ("post", "put", "patch", "delete") and not is_login and not is_upload and not is_webhook

    parameters = copy.deepcopy(list(params or []) + list(query or []))
    if idem:
        parameters.append(PR("IdempotencyKey"))
    if is_webhook:
        parameters.append({
            "name": "X-Signature", "in": "header", "required": True,
            "description": "渠道回调签名；使用渠道密钥对原始报文验签，验签失败拒绝处理并记录。",
            "schema": {"type": "string"},
        })
    parameters += list(headers or [])

    responses = {}
    if ok == 204:
        responses["204"] = {"description": ok_desc or "操作成功，无返回体"}
    else:
        if list_of is not None:
            payload = {
                "type": "object",
                "description": "统一分页响应",
                "required": ["items", "meta"],
                "properties": {"items": A(R(list_of)), "meta": R("PageMeta")},
            }
        elif isinstance(schema, str):
            payload = R(schema)
        else:
            payload = schema
        responses[str(ok)] = {
            "description": ok_desc or "成功",
            "content": {"application/json": {"schema": payload}},
        }
    for code, name in _error_responses:
        responses[code] = RS(name)

    operation = {
        "tags": [tag],
        "summary": summary,
        "operationId": _oid(method, path),
        "responses": responses,
    }
    if desc:
        operation["description"] = desc
    if parameters:
        operation["parameters"] = parameters
    if body is not None:
        bschema = R(body) if isinstance(body, str) else body
        operation["requestBody"] = {"required": body_required, "content": {body_ct: {"schema": bschema}}}
    if security is not None:
        operation["security"] = security
    elif public:
        operation["security"] = []
    item[method] = operation


# ---- 路径参数快捷方式 -----------------------------------------------------
PID = {"name": "id", "in": "path", "required": True, "description": "资源 ID", "schema": idf()}
PID_STR = {"name": "id", "in": "path", "required": True, "description": "资源 ID", "schema": {"type": "string"}}


def qp(name, schema, desc, required=False):
    return {"name": name, "in": "query", "required": required, "description": desc, "schema": schema}


def pp(name, desc, schema=None, required=True):
    return {"name": name, "in": "path", "required": required, "description": desc, "schema": schema or idf()}


PAGE_Q = [PR("Page"), PR("PageSize")]
CURSOR_Q = [PR("Cursor"), PR("Limit")]

# ============================ /auth/* =====================================
add("/auth/staff/login", "post", T_AUTH, "员工登录", body="StaffLoginRequest", schema="TokenPair", public=True,
    desc="企业管理员、电商运营、库存仓管、售后专员、财务只读审计、客服主管使用账号密码登录。登录接口不要求 Idempotency-Key。")
add("/auth/customer/login", "post", T_AUTH, "客户登录", body="CustomerLoginRequest", schema="TokenPair", public=True,
    desc="C 端客户使用手机号 + 密码或短信验证码登录。")
add("/auth/customer/register", "post", T_AUTH, "客户注册", body="CustomerRegisterRequest", ok=201, schema="Customer", public=True,
    desc="C 端客户注册并创建客户档案；同时建立官方商城渠道身份。")
add("/auth/guest-session", "post", T_AUTH, "游客会话", body="GuestSessionRequest", schema="TokenPair", public=True,
    desc="未注册访客获取游客令牌，用于浏览商品与加购；下单需转为客户身份。")
add("/auth/refresh", "post", T_AUTH, "刷新令牌", body="RefreshRequest", schema="TokenPair", public=True,
    desc="使用 refresh_token 换取新的令牌对；refresh_token 一次性轮换，旧令牌立即失效。")
add("/auth/logout", "post", T_AUTH, "退出登录", ok=204, security=[{"bearerAuth": []}],
    desc="吊销当前访问令牌及刷新令牌族。")
add("/auth/me", "get", T_AUTH, "当前登录主体", schema="CurrentUser", security=[{"bearerAuth": []}],
    desc="返回当前主体、角色、权限码与渠道数据范围。")
add("/auth/password/change", "post", T_AUTH, "修改密码", body="PasswordChangeRequest", ok=204, security=[{"bearerAuth": []}],
    desc="修改当前登录主体密码；成功后吊销其他会话的刷新令牌。")

# ======================= 组织与权限 =======================================
add("/staff/users", "get", T_STAFF, "员工列表", query=PAGE_Q + [
    qp("keyword", {"type": "string"}, "按登录名/姓名/邮箱模糊搜索"),
    qp("status", E(["ACTIVE", "DISABLED", "LOCKED", "PENDING"]), "账号状态"),
    qp("role_code", E(ROLE_CODES), "按角色码过滤"),
], list_of="StaffUser", desc="需要 shared:staff:read 权限。")
add("/staff/users", "post", T_STAFF, "创建员工", body="StaffUserCreateRequest", ok=201, schema="StaffUser",
    desc="需要 shared:staff:write 权限。")
add("/staff/users/{id}", "get", T_STAFF, "员工详情", params=[PID], schema="StaffUser", desc="需要 shared:staff:read 权限。")
add("/staff/users/{id}", "patch", T_STAFF, "更新员工", params=[PID], body="StaffUserUpdateRequest", schema="StaffUser",
    desc="需要 shared:staff:write 权限。")
add("/staff/users/{id}/disable", "post", T_STAFF, "停用员工", params=[PID], ok=204,
    desc="停用后该员工所有令牌失效，禁止登录；需要 shared:staff:write 权限。")
add("/staff/users/{id}/roles", "get", T_STAFF, "查询员工角色", params=[PID], schema="StaffUserRoles",
    desc="需要 shared:staff:read 权限。")
add("/staff/users/{id}/roles", "put", T_STAFF, "设置员工角色", params=[PID], body="StaffUserRoles", schema="StaffUserRoles",
    desc="全量覆盖员工角色；需要 shared:role:write 权限，变更写审计。")
add("/staff/users/{id}/channel-scopes", "get", T_STAFF, "查询员工渠道范围", params=[PID], schema="StaffChannelScopes",
    desc="需要 shared:staff:read 权限。")
add("/staff/users/{id}/channel-scopes", "put", T_STAFF, "设置员工渠道范围", params=[PID], body="StaffChannelScopes", schema="StaffChannelScopes",
    desc="全量覆盖员工的渠道数据范围；需要 shared:staff:write 权限。")
add("/roles", "get", T_STAFF, "角色列表", query=PAGE_Q, list_of="Role", desc="需要 shared:role:read 权限。")
add("/permissions", "get", T_STAFF, "权限字典", query=PAGE_Q, list_of="Permission", desc="需要 shared:role:read 权限。")

# ======================= 渠道账号 =========================================
add("/channel-accounts", "get", T_CHANNEL, "渠道账号列表", query=PAGE_Q + [
    qp("channel_type", E(CHANNEL_TYPES), "渠道类型"),
    qp("status", E(["ACTIVE", "DISABLED"]), "状态"),
], list_of="ChannelAccount", desc="需要 shop:channel:read 权限；员工只能看到自己渠道范围内的渠道。")
add("/channel-accounts", "post", T_CHANNEL, "创建渠道账号", body="ChannelAccountCreateRequest", ok=201, schema="ChannelAccount",
    desc="需要 shop:channel:write 权限。")
add("/channel-accounts/{id}", "patch", T_CHANNEL, "更新渠道账号", params=[PID], body="ChannelAccountUpdateRequest", schema="ChannelAccount",
    desc="需要 shop:channel:write 权限。")

# ======================= 商品中心 =========================================
add("/brands", "get", T_CATALOG, "品牌列表", query=PAGE_Q, list_of="Brand", desc="需要 shop:product:read 权限。")
add("/brands", "post", T_CATALOG, "创建品牌", body="BrandCreateRequest", ok=201, schema="Brand", desc="需要 shop:product:write 权限。")
add("/categories", "get", T_CATALOG, "分类列表/分类树", query=[qp("parent_id", idf(), "父分类 ID；不传返回完整树")],
    schema=A(R("Category")), desc="需要 shop:product:read 权限。")
add("/categories", "post", T_CATALOG, "创建分类", body="CategoryCreateRequest", ok=201, schema="Category", desc="需要 shop:product:write 权限。")
add("/categories", "patch", T_CATALOG, "更新分类", body="CategoryUpdateRequest", schema="Category",
    desc="按请求体中的 id 更新分类；需要 shop:product:write 权限。")
add("/products", "get", T_CATALOG, "商品列表", query=PAGE_Q + [
    qp("keyword", {"type": "string"}, "名称/SPU 编码模糊搜索"),
    qp("status", E(["DRAFT", "ON_SALE", "OFF_SHELF", "ARCHIVED"]), "商品状态"),
    qp("category_id", idf(), "分类 ID"),
    qp("brand_id", idf(), "品牌 ID"),
    qp("product_type", s(), "产品类型"),
], list_of="Product", desc="需要 shop:product:read 权限。")
add("/products", "post", T_CATALOG, "创建商品", body="ProductCreateRequest", ok=201, schema="Product", desc="需要 shop:product:write 权限。")
add("/products/search", "get", T_CATALOG, "商品搜索", query=PAGE_Q + [
    qp("q", s("搜索关键词"), "关键词，使用 pg_trgm 相似度检索", required=True),
    qp("channel_account_id", idf(), "限定渠道"),
], list_of="Product", desc="基于 pg_trgm 的商品名/型号模糊搜索，面向运营与客服工作台。需要 shop:product:read 权限。")
add("/products/{id}", "get", T_CATALOG, "商品详情（管理端）", params=[PID], schema="Product", desc="需要 shop:product:read 权限。")
add("/products/{id}", "patch", T_CATALOG, "更新商品", params=[PID], body="ProductUpdateRequest", schema="Product", desc="需要 shop:product:write 权限。")
add("/products/{id}/publish", "post", T_CATALOG, "上架商品", params=[PID], schema="Product",
    desc="DRAFT/OFF_SHELF -> ON_SALE，校验 SKU、价格与媒体完整性；需要 shop:product:write 权限。")
add("/products/{id}/unpublish", "post", T_CATALOG, "下架商品", params=[PID], schema="Product",
    desc="ON_SALE -> OFF_SHELF，不影响已生成订单；需要 shop:product:write 权限。")
add("/products/{id}/skus", "get", T_CATALOG, "商品 SKU 列表", params=[PID], query=PAGE_Q, list_of="Sku", desc="需要 shop:product:read 权限。")
add("/products/{id}/skus", "post", T_CATALOG, "新增 SKU", params=[PID], body="SkuCreateRequest", ok=201, schema="Sku",
    desc="需要 shop:product:write 权限。")
add("/skus/{id}", "patch", T_CATALOG, "更新 SKU", params=[PID], body="SkuUpdateRequest", schema="Sku",
    desc="价格变更写入 price_change_log 并审计；需要 shop:product:write 权限。")
add("/products/{id}/public", "get", T_CATALOG, "商品公开详情（C 端）", params=[PID], schema="ProductPublic",
    desc="返回已上架商品的脱敏公开视图，游客令牌亦可访问，用于官方商城/旗舰店商品详情页。")
add("/attachments", "post", T_ATTACH, "上传附件", body={
    "type": "object", "required": ["file"],
    "properties": {
        "file": {"type": "string", "format": "binary", "description": "文件，单文件不超过 20 MiB"},
        "owner_type": s("归属资源类型"),
        "owner_id": s("归属资源 ID"),
        "is_public": b("是否公开可读", default=False),
    },
}, body_ct="multipart/form-data", ok=201, schema="Attachment",
    desc="Multipart 上传到对象存储（MinIO 兼容 S3），返回附件记录；上传接口不要求 Idempotency-Key。")
add("/attachments/{id}", "get", T_ATTACH, "附件详情", params=[PID], schema="Attachment")

# ======================= 库存中心 =========================================
add("/warehouses", "get", T_INV, "仓库列表", query=PAGE_Q, list_of="Warehouse", desc="需要 shop:inventory:read 权限。")
add("/warehouses", "post", T_INV, "创建仓库", body="WarehouseCreateRequest", ok=201, schema="Warehouse", desc="需要 shop:inventory:write 权限。")
add("/inventory", "get", T_INV, "库存查询", query=PAGE_Q + [
    qp("warehouse_id", idf(), "仓库 ID"),
    qp("sku_id", idf(), "SKU ID"),
    qp("sku_code", {"type": "string"}, "SKU 编码"),
    qp("category_id", idf(), "分类 ID"),
    qp("low_stock", {"type": "boolean"}, "仅返回可售数量 <= 安全库存的结存"),
], list_of="InventoryItem", desc="查询可售/锁定/在途/安全库存。需要 shop:inventory:read 权限。")
add("/inventory/adjust", "post", T_INV, "库存调整", body="StockAdjustRequest", ok=201, schema="InventoryLedgerEntry",
    desc="带乐观锁版本号的库存调整，成功后写入只追加流水 inventory_ledger；需要 shop:inventory:write 权限。")
add("/inventory/ledger", "get", T_INV, "库存流水", query=CURSOR_Q + [
    qp("sku_id", idf(), "SKU ID"),
    qp("warehouse_id", idf(), "仓库 ID"),
    qp("change_type", s(), "变动类型"),
    qp("created_from", dt(), "起始时间"),
    qp("created_to", dt(), "结束时间"),
], schema={"type": "object", "required": ["items", "meta"], "properties": {
    "items": A(R("InventoryLedgerEntry")), "meta": R("PageMeta")}},
    desc="只追加库存流水；数据量大，使用 cursor + limit 游标分页，返回 meta.next_cursor。需要 shop:inventory:read 权限。")
add("/inventory/alerts", "get", T_INV, "低库存预警", query=PAGE_Q + [qp("warehouse_id", idf(), "仓库 ID")],
    list_of="InventoryItem", desc="可售数量低于或等于安全库存的结存。需要 shop:inventory:read 权限。")

# ======================= 客户中心 =========================================
add("/customers", "get", T_CUST, "客户列表", query=PAGE_Q + [
    qp("keyword", {"type": "string"}, "客户编号/手机号/昵称搜索"),
    qp("status", E(["ACTIVE", "DISABLED"]), "客户状态"),
    qp("channel_account_id", idf(), "首次注册渠道"),
], list_of="Customer", desc="需要 shop:customer:read 权限。")
add("/customers/{id}", "get", T_CUST, "客户详情", params=[PID], schema="Customer", desc="需要 shop:customer:read 权限，敏感字段脱敏。")
add("/customers/{id}", "patch", T_CUST, "更新客户", params=[PID], body="CustomerUpdateRequest", schema="Customer",
    desc="需要 shop:customer:write 权限，变更写审计。")
add("/customers/{id}/addresses", "get", T_CUST, "客户地址列表", params=[PID], schema=A(R("CustomerAddress")), desc="需要 shop:customer:read 权限。")
add("/customers/{id}/addresses", "post", T_CUST, "新增客户地址", params=[PID], body="CustomerAddressRequest", ok=201,
    schema="CustomerAddress", desc="需要 shop:customer:write 权限。")
add("/customers/addresses/{id}", "patch", T_CUST, "更新客户地址", params=[PID], body="CustomerAddressRequest", schema="CustomerAddress",
    desc="需要 shop:customer:write 权限。")
add("/customers/addresses/{id}", "delete", T_CUST, "删除客户地址", params=[PID], ok=204, desc="软删除；需要 shop:customer:write 权限。")
add("/customers/{id}/orders", "get", T_CUST, "客户订单", params=[PID], query=PAGE_Q + [
    qp("status", E(ORDER_STATUS), "订单业务状态"),
], list_of="Order", desc="需要 shop:order:read 权限，且仅能查看自身渠道范围内的客户。")

# ======================= 购物车 ===========================================
add("/cart", "get", T_CART, "查看购物车", query=[qp("channel_account_id", idf(), "渠道账号 ID")], schema="Cart",
    desc="返回当前客户在指定渠道的未结算购物车；自动创建空购物车。")
add("/cart/items", "post", T_CART, "加入购物车", body="CartItemAddRequest", ok=201, schema="Cart",
    desc="同 SKU 累加数量，单条数量上限 999。")
add("/cart/items/{id}", "patch", T_CART, "更新购物车条目", params=[PID], body="CartItemUpdateRequest", schema="Cart")
add("/cart/items/{id}", "delete", T_CART, "删除购物车条目", params=[PID], ok=204)

# ======================= 订单中心 =========================================
add("/orders", "post", T_ORDER, "创建订单", body="CreateOrderRequest", ok=201, schema="Order",
    desc="校验渠道、地址、价格与库存后创建订单并锁定库存；初始 status=CREATED、payment_status=UNPAID、fulfillment_status=UNSHIPPED、after_sales_status=NONE。需要 shop:order:write 权限（客户下单为其本人订单）。")
add("/orders", "get", T_ORDER, "订单列表", query=PAGE_Q + [
    qp("order_no", {"type": "string"}, "订单号"),
    qp("status", E(ORDER_STATUS), "订单业务状态"),
    qp("payment_status", E(PAYMENT_STATUS), "支付状态"),
    qp("fulfillment_status", E(FULFILLMENT_STATUS), "履约状态"),
    qp("after_sales_status", E(AFTER_SALES_STATUS), "售后状态"),
    qp("channel_account_id", idf(), "渠道账号 ID"),
    qp("customer_id", idf(), "客户 ID"),
    qp("created_from", dt(), "下单起始时间"),
    qp("created_to", dt(), "下单结束时间"),
], list_of="Order", desc="员工按渠道范围过滤；客户仅返回本人订单。需要 shop:order:read 权限。")
add("/orders/{id}", "get", T_ORDER, "订单详情", params=[PID], schema="Order", desc="需要 shop:order:read 权限或资源归属校验。")
add("/orders/{id}/cancel", "post", T_ORDER, "取消订单", params=[PID], body="OrderCancelRequest", schema="Order",
    desc="仅 CREATED/PENDING_PAYMENT/PAID（未履约）可取消，取消后释放库存锁定；非法状态返回 409。需要 shop:order:write 权限。")
add("/orders/{id}/confirm-receipt", "post", T_ORDER, "确认收货", params=[PID], schema="Order",
    desc="客户确认收货，订单进入 COMPLETED；需要资源归属校验。")
add("/orders/{id}/address", "patch", T_ORDER, "修改收货地址", params=[PID], body="OrderAddressUpdateRequest", schema="Order",
    desc="仅未发货订单可改址；需要 shop:order:write 权限或客户归属校验。")
add("/orders/{id}/remark", "patch", T_ORDER, "修改订单备注", params=[PID], body="OrderRemarkUpdateRequest", schema="Order",
    desc="区分买家备注与商家备注；需要 shop:order:write 权限。")
add("/orders/{id}/timeline", "get", T_ORDER, "订单状态时间线", params=[PID], query=CURSOR_Q,
    schema={"type": "object", "required": ["items", "meta"], "properties": {"items": A(R("OrderTimelineEntry")), "meta": R("PageMeta")}},
    desc="返回四条状态线的全部变更历史（order_status_history）。数据可能较多，使用 cursor + limit 游标分页。需要 shop:order:read 权限。")
add("/orders/{id}/ship", "post", T_ORDER, "订单发货", params=[PID], body="ShipRequest", ok=201, schema="Shipment",
    desc="创建包裹并更新履约状态，支持部分发货（PARTIAL_SHIPPED）与多包裹；需要 shop:fulfillment:write 权限。")

# ======================= 支付中心 =========================================
add("/payments", "post", T_PAY, "创建支付单", body="PaymentCreateRequest", ok=201, schema="Payment",
    desc="为订单创建支付单并返回收银台地址；金额以订单应付金额为准，禁止浮点。需要 shop:payment:read 权限（客户支付本人订单）。")
add("/payments", "get", T_PAY, "支付单列表", query=PAGE_Q + [
    qp("order_id", idf(), "订单 ID"),
    qp("status", E(["PENDING", "SUCCESS", "FAILED", "CLOSED"]), "支付单状态"),
    qp("method", s(), "支付方式"),
], list_of="Payment", desc="需要 shop:payment:read 权限。")
add("/payments/{id}", "get", T_PAY, "支付单详情", params=[PID], schema="Payment", desc="需要 shop:payment:read 权限。")
add("/payments/{id}/mock-succeed", "post", T_PAY, "模拟支付成功", params=[PID], body="MockPaymentSucceedRequest", schema="Payment",
    desc="仅 MOCK 渠道且非生产环境可用，用于联调与演示；会更新订单 payment_status。需要 shop:payment:read 权限。")
add("/webhooks/payment/{channel}", "post", T_PAY, "支付渠道回调", params=[pp("channel", "支付渠道编码", schema=s())],
    body="PaymentCallback", schema="WebhookAck", public=True,
    desc="渠道异步通知。按 event_id 去重、验签后落 payment_callback_log，并幂等更新支付单与订单；回调接口不要求 Idempotency-Key。")

# ======================= 履约与物流 =======================================
add("/carriers", "get", T_FUL, "承运商列表", query=PAGE_Q, list_of="Carrier", desc="需要 shop:fulfillment:write 权限。")
add("/shipments", "get", T_FUL, "包裹列表", query=PAGE_Q + [
    qp("order_id", idf(), "订单 ID"),
    qp("status", E(["PENDING", "PICKED_UP", "IN_TRANSIT", "DELIVERED", "EXCEPTION", "RETURNED"]), "包裹状态"),
    qp("carrier_code", {"type": "string"}, "承运商编码"),
    qp("tracking_no", {"type": "string"}, "运单号"),
], list_of="Shipment", desc="需要 shop:fulfillment:write 权限。")
add("/shipments/{id}", "get", T_FUL, "包裹详情", params=[PID], schema="Shipment", desc="返回包裹明细与轨迹事件。需要 shop:fulfillment:write 权限。")
add("/shipments/{id}/tracking-events", "post", T_FUL, "登记物流轨迹", params=[PID], body="TrackingEventCreateRequest", ok=201,
    schema="TrackingEvent", desc="人工补录物流轨迹，同 (shipment_id, event_time, description) 去重；需要 shop:fulfillment:write 权限。")
add("/webhooks/logistics/{carrier}", "post", T_FUL, "物流承运商回调", params=[pp("carrier", "承运商编码", schema=s())],
    body="LogisticsCallback", schema="WebhookAck", public=True,
    desc="承运商轨迹推送，验签、去重后追加 tracking_event 并更新包裹状态；回调接口不要求 Idempotency-Key。")

# ======================= 售后中心 =========================================
add("/after-sales/applications", "post", T_AS, "提交售后申请", body="AfterSalesCreateRequest", ok=201, schema="AfterSalesApplication",
    desc="客户提交退款/退货退款/维修/换货/安装/保修申请，初始 status=APPLYING，并同步订单 after_sales_status。")
add("/after-sales/applications", "get", T_AS, "售后申请列表", query=PAGE_Q + [
    qp("status", E(AFTER_SALES_APPLICATION_STATUS), "售后状态"),
    qp("type", s(), "售后类型"),
    qp("order_id", idf(), "订单 ID"),
    qp("customer_id", idf(), "客户 ID"),
], list_of="AfterSalesApplication", desc="需要 shop:aftersales:read 权限；客户仅返回本人申请。")
add("/after-sales/applications/{id}", "get", T_AS, "售后申请详情", params=[PID], schema="AfterSalesApplication",
    desc="返回售后单、凭证、处理记录与沟通消息。需要 shop:aftersales:read 权限。")
add("/after-sales/applications/{id}/review", "post", T_AS, "审核售后申请", params=[PID], body="ReviewRequest",
    schema="AfterSalesApplication", desc="APPLYING -> PROCESSING 或 REJECTED；需要 shop:aftersales:review 权限。")
add("/after-sales/applications/{id}/return-shipment", "post", T_AS, "登记退货物流", params=[PID], body="ReturnShipmentRequest",
    schema="AfterSalesApplication", desc="客户寄回后登记退货承运商与运单号；需要 shop:aftersales:review 权限或客户归属校验。")
add("/after-sales/applications/{id}/receive", "post", T_AS, "确认收到退货", params=[PID], body="AfterSalesReceiveRequest",
    schema="AfterSalesApplication", desc="仓库确认收货并验收；需要 shop:aftersales:review 权限。")
add("/after-sales/applications/{id}/complete", "post", T_AS, "完成售后", params=[PID], body="AfterSalesCompleteRequest",
    schema="AfterSalesApplication", desc="PROCESSING -> COMPLETED，可触发退款；需要 shop:aftersales:review 权限。")
add("/after-sales/applications/{id}/cancel", "post", T_AS, "取消售后申请", params=[PID], body="AfterSalesCancelRequest",
    schema="AfterSalesApplication", desc="客户或客服在不满足条件时取消申请；需要资源归属校验或 shop:aftersales:review 权限。")
add("/after-sales/applications/{id}/messages", "post", T_AS, "新增售后沟通消息", params=[PID], body="AfterSalesMessageCreateRequest",
    ok=201, schema="AfterSalesMessage", desc="客户与客服在售后单内留言；需要 shop:aftersales:read 权限或客户归属校验。")

# ======================= 退款 =============================================
add("/refunds", "get", T_REFUND, "退款单列表", query=PAGE_Q + [
    qp("order_id", idf(), "订单 ID"),
    qp("status", E(["PENDING", "PROCESSING", "SUCCESS", "FAILED", "CANCELLED"]), "退款状态"),
], list_of="Refund", desc="需要 shop:aftersales:read 权限。")
add("/refunds/{id}", "get", T_REFUND, "退款单详情", params=[PID], schema="Refund", desc="需要 shop:aftersales:read 权限。")
add("/refunds", "post", T_REFUND, "发起退款", body="RefundCreateRequest", ok=201, schema="Refund",
    desc="按售后单或订单发起退款；金额不得超过可退金额，退款同步更新订单 payment_status=REFUNDING/REFUNDED。需要 shop:aftersales:review 权限。")
add("/refunds/{id}/execute", "post", T_REFUND, "执行退款", params=[PID], schema="Refund",
    desc="调用渠道退款并记录 RefundAttempt；必须幂等，禁止重复向渠道发起。需要 shop:aftersales:review 权限。")
add("/refunds/{id}/attempts", "get", T_REFUND, "退款尝试记录", params=[PID], query=PAGE_Q, list_of="RefundAttempt",
    desc="返回每次渠道退款的请求、应答与结果，用于对账与排障。需要 shop:aftersales:read 权限。")
add("/webhooks/refund/{channel}", "post", T_REFUND, "退款渠道回调", params=[pp("channel", "退款渠道编码", schema=s())],
    body="RefundCallback", schema="WebhookAck", public=True,
    desc="退款结果异步通知，验签去重后更新退款单与尝试记录；回调接口不要求 Idempotency-Key。")

# ======================= 发票 =============================================
add("/invoices", "get", T_INVOICE, "发票列表", query=PAGE_Q + [
    qp("order_id", idf(), "订单 ID"),
    qp("status", E(["DRAFT", "PENDING", "ISSUED", "VOID"]), "发票状态"),
    qp("type", s(), "发票类型"),
], list_of="Invoice", desc="需要 shop:invoice:read 权限。")
add("/invoices", "post", T_INVOICE, "申请开票", body="InvoiceCreateRequest", ok=201, schema="Invoice",
    desc="客户或财务为订单申请开票，初始 status=PENDING；需要 shop:invoice:write 权限。")
add("/invoices/{id}", "get", T_INVOICE, "发票详情", params=[PID], schema="Invoice", desc="需要 shop:invoice:read 权限。")
add("/invoices/{id}/issue", "post", T_INVOICE, "开具发票", params=[PID], body="InvoiceIssueRequest", schema="Invoice",
    desc="PENDING -> ISSUED，登记发票号码与电子发票附件；需要 shop:invoice:write 权限。")
add("/invoices/{id}/void", "post", T_INVOICE, "作废/红冲发票", params=[PID], body="InvoiceVoidRequest", schema="Invoice",
    desc="ISSUED -> VOID，或开具红冲票；需要 shop:invoice:write 权限，变更写审计。")

# ======================= 报表 =============================================
rpt_q = [qp("date_from", date(), "起始日期", required=True), qp("date_to", date(), "结束日期", required=True),
         qp("channel_account_id", idf(), "渠道账号 ID")]
add("/reports/dashboard", "get", T_REPORT, "经营看板", query=rpt_q, schema="DashboardReport",
    desc="销售、订单、客户、库存预警与售后的汇总指标。需要 shop:report:read 权限。")
add("/reports/sales/daily", "get", T_REPORT, "销售日报", query=rpt_q + PAGE_Q, list_of="SalesDailyReport",
    desc="按日汇总销售数据。需要 shop:report:read 权限。")
add("/reports/inventory", "get", T_REPORT, "库存报表", query=[qp("warehouse_id", idf(), "仓库 ID"), qp("category_id", idf(), "分类 ID")],
    schema="InventoryReport", desc="按仓库与品类汇总库存与预警。需要 shop:inventory:read 权限。")
add("/reports/after-sales", "get", T_REPORT, "售后报表", query=[qp("date_from", date(), "起始日期", required=True),
    qp("date_to", date(), "结束日期", required=True), qp("status", E(AFTER_SALES_STATUS), "售后状态"),
    qp("type", s(), "售后类型")], schema="AfterSalesReport",
    desc="售后申请量、处理时长与退款汇总。需要 shop:aftersales:read 权限。")

# ======================= 审计与系统 =======================================
add("/audit-logs", "get", T_SYS, "审计日志", query=CURSOR_Q + [
    qp("actor_type", E(["STAFF", "CUSTOMER", "GUEST", "SYSTEM"]), "操作者类型"),
    qp("actor_id", idf(), "操作者 ID"),
    qp("action", {"type": "string"}, "动作，例如 order.cancel"),
    qp("resource_type", {"type": "string"}, "资源类型，例如 Order"),
    qp("resource_id", {"type": "string"}, "资源 ID"),
    qp("request_id", {"type": "string"}, "请求追踪 ID"),
    qp("created_from", dt(), "起始时间"),
    qp("created_to", dt(), "结束时间"),
], schema={"type": "object", "required": ["items", "meta"], "properties": {"items": A(R("AuditLog")), "meta": R("PageMeta")}},
    desc="审计日志数据量大，使用 cursor + limit 游标分页，返回 meta.next_cursor。需要 shared:audit:read 权限。")
add("/system/health", "get", T_SYS, "健康检查", schema="SystemHealth",
    desc="探测 PostgreSQL 17（含 pgvector/pg_trgm/pgcrypto）、Redis 7 与对象存储连通性。")
add("/system/version", "get", T_SYS, "版本信息", schema="VersionInfo", desc="返回服务与 API 版本信息。")


# --------------------------------------------------------------------------
# 组装文档
# --------------------------------------------------------------------------
INFO_DESC = """栖云智家科技有限公司第一期企业电商基础平台 API。

- 企业产品：智能门锁、家用摄像头、清洁机器人、智能灯具、家庭网关、配件耗材，以及云服务、上门安装与维修服务。
- 销售渠道：官方商城、电商官方旗舰店、授权零售门店。
- 第一期范围：商品、客户、库存、订单、支付、履约、售后、发票、组织权限、审计。**不包含**智能客服、RAG、本体与工具调用。
- 本期预留扩展点：shared.outbox_event 领域事件表、knowledge 保留 schema（pgvector 0.8.7 已启用）、pg_trgm 全文检索、pgcrypto 加密能力；业务表与事件均为后续阶段可消费的数据底座。
- 技术栈：Python 3.11 + FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic + psycopg3 + PostgreSQL 17 + Redis 7 + MinIO 兼容 S3；保持 Python 单体多模块，便于后续扩展。
- 数据库模式：单库多 schema —— shared（身份/权限/渠道/审计/附件/幂等/outbox）、commerce（一期业务表）、knowledge（预留，本期不写入）。
- 金额：numeric(14,2)，币种固定 CNY；JSON 中以字符串传输，禁止浮点。
- 库存：可售/锁定/在途/安全库存，任何变动写入只追加流水。
- 幂等：除登录、上传与 webhook 外，所有写接口必须携带 Idempotency-Key，写入 shared.idempotency_record；同 key 同指纹回放，异指纹返回 409。
- 分页：标准分页 page(>=1) + page_size(1..100)，响应含 PageMeta；审计日志、库存流水、订单时间线等大列表使用 cursor + limit 游标分页并返回 meta.next_cursor。
- 错误：统一 ApiError{code,message,details?,request_id}，覆盖 400/401/403/404/409/422/429/500。
- 认证：JWT bearerAuth；/auth/* 的登录/注册/游客/刷新与 /webhooks/* 免默认鉴权，其余接口默认要求 Bearer 令牌。
- 一期角色：企业管理员、电商运营、库存/仓管、售后专员、财务/只读审计、客服主管；客户为 C 端用户。权限码示例：shop:product:read|write、shop:inventory:read|write、shop:order:read|write、shop:payment:read、shop:fulfillment:write、shop:aftersales:read|review、shop:invoice:read|write、shop:customer:read|write、shared:staff:read|write、shared:audit:read。
- 元数据脱敏：手机号、真实姓名、银行卡号等按权限脱敏返回；不存储完整支付敏感信息。
- 状态机：order.status(CREATED/PENDING_PAYMENT/PAID/FULFILLING/SHIPPED/COMPLETED/CANCELLED/CLOSED)；payment_status(UNPAID/PARTIAL/PAID/REFUNDING/REFUNDED)；fulfillment_status(UNSHIPPED/PARTIAL_SHIPPED/SHIPPED/DELIVERED)；after_sales_status(NONE/APPLYING/PROCESSING/COMPLETED/REJECTED)。"""

spec = {
    "openapi": "3.1.0",
    "info": {
        "title": "栖云智家科技有限公司 · 第一期企业电商基础平台 API",
        "version": "1.0.0",
        "description": INFO_DESC,
        "contact": {"name": "栖云智家科技有限公司"},
        "license": {"name": "Proprietary"},
    },
    "servers": [
        {"url": "http://localhost:8000/api/v1", "description": "本地开发环境"},
    ],
    "security": [{"bearerAuth": []}],
    "tags": [{"name": n, "description": d} for n, d in TAGS],
    "paths": PATHS,
    "components": {
        "securitySchemes": SECURITY_SCHEMES,
        "parameters": PARAMS,
        "responses": RESPS,
        "schemas": S,
    },
    "x-platform": {
        "company": "栖云智家科技有限公司",
        "module": "企业电商基础平台",
        "phase": 1,
        "database_schemas": ["shared", "commerce", "knowledge"],
        "postgresql": "17",
        "extensions_available": ["pgvector 0.8.7", "pg_trgm", "pgcrypto"],
        "currency": "CNY",
        "money_type": "numeric(14,2) (JSON 字符串)",
        "idempotency_store": "shared.idempotency_record",
        "outbox": {
            "table": "shared.outbox_event",
            "phase_1_behavior": "本期只写不消费，作为下游事件消费的预留出口",
            "event_types": [
                "order.created", "order.paid", "order.cancelled", "order.shipped", "order.completed",
                "payment.succeeded", "payment.failed",
                "shipment.created", "shipment.delivered", "tracking.updated",
                "after_sales.applied", "after_sales.reviewed", "after_sales.completed",
                "refund.created", "refund.succeeded", "refund.failed",
                "invoice.issued", "invoice.voided",
                "inventory.adjusted", "inventory.low_stock",
                "product.published", "product.unpublished",
                "customer.registered",
            ],
        },
        "reserved_for_later_phases": {
            "phase_2_knowledge_base": "knowledge schema 已保留，本期不提供接口",
            "phase_3_rag_customer_service": "动态事实查询可复用本期只读接口，写操作沿用幂等与审计",
            "phase_4_ontology_and_tools": "工具调用通过 outbox_event 与审计日志闭环，本期不实现",
            "pgvector": "0.8.7 已启用，供知识切片向量检索使用",
        },
    },
}


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        yaml.safe_dump(spec, f, allow_unicode=True, sort_keys=False, default_flow_style=False, width=100000)
    path_count = len(spec["paths"])
    op_count = sum(len([m for m in item if m in ("get", "post", "put", "patch", "delete")]) for item in spec["paths"].values())
    print("written:", OUT)
    print("paths:", path_count, "operations:", op_count, "schemas:", len(spec["components"]["schemas"]))
    return OUT


if __name__ == "__main__":
    main()
