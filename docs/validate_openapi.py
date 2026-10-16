#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验《栖云智家_第一期_openapi.yaml》。

检查项：
  1. 文件可被 python3 作为合法 YAML 加载；
  2. openapi 字段必须为 3.1.0；
  3. 每个 path 至少包含一个 HTTP operation；
  4. 所有 $ref 都能解析到文档内已存在的键；
  5. 需求指定的 components.schemas 全部存在；
  6. 订单/售后状态机枚举与事实卡完全一致；
  7. 写接口（除登录、上传、webhook）声明 Idempotency-Key；
  8. 每个 operation 都声明 400/401/403/404/409/422/429/500 响应。
用法：python3 validate_openapi.py [yaml路径]
"""
import sys
import yaml

DEFAULT_YAML = "/Users/jianbinzhou/Documents/智能客服调研/output/栖云智家_第一期_openapi.yaml"
YAML_PATH = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_YAML

METHODS = ("get", "post", "put", "patch", "delete", "head", "options", "trace")
WRITE_METHODS = ("post", "put", "patch", "delete")

REQUIRED_SCHEMAS = [
    "ApiError", "PageMeta", "StaffUser", "Role", "Permission", "ChannelAccount",
    "Brand", "Category", "Product", "ProductMedia", "ProductAttribute", "Sku",
    "Warehouse", "InventoryItem", "InventoryLedgerEntry", "StockAdjustRequest",
    "Customer", "CustomerAddress", "Cart", "CartItem", "Order", "OrderItem",
    "OrderTimelineEntry", "CreateOrderRequest", "ShipRequest", "Payment",
    "PaymentCallback", "Carrier", "Shipment", "ShipmentItem", "TrackingEvent",
    "AfterSalesApplication", "AfterSalesMessage", "ReviewRequest", "Refund",
    "RefundAttempt", "Invoice", "AuditLog", "Attachment", "DashboardReport",
    "SalesDailyReport",
]

ERROR_CODES = ["400", "401", "403", "404", "409", "422", "429", "500"]

EXPECTED = {
    "Order.status": ["CREATED", "PENDING_PAYMENT", "PAID", "FULFILLING", "SHIPPED", "COMPLETED", "CANCELLED", "CLOSED"],
    "Order.payment_status": ["UNPAID", "PARTIAL", "PAID", "REFUNDING", "PARTIAL_REFUNDED", "REFUNDED"],
    "Order.fulfillment_status": ["UNSHIPPED", "PARTIAL_SHIPPED", "SHIPPED", "DELIVERED"],
    "Order.after_sales_status": ["NONE", "APPLYING", "PROCESSING", "COMPLETED", "REJECTED"],
    "AfterSalesApplication.status": ["SUBMITTED", "REVIEWING", "APPROVED", "REJECTED", "WAITING_RETURN", "RETURN_SHIPPED", "RECEIVED", "REFUNDING", "COMPLETED", "CANCELLED"],
}

errors = []
warnings = []


def check(cond, msg):
    if not cond:
        errors.append(msg)


# 1. YAML 可加载
with open(YAML_PATH, encoding="utf-8") as f:
    doc = yaml.safe_load(f)
check(isinstance(doc, dict), "YAML 根节点不是映射")

# 2. openapi 版本
check(doc.get("openapi") == "3.1.0", "openapi 字段不是 3.1.0：%r" % doc.get("openapi"))
check(doc.get("servers") and doc["servers"][0].get("url") == "http://localhost:8000/api/v1",
      "servers[0].url 不是 http://localhost:8000/api/v1")
check(doc.get("security") == [{"bearerAuth": []}], "根级 security 不是 bearerAuth")

# 3. 每个 path 至少一个 operation
paths = doc.get("paths") or {}
path_count = len(paths)
op_count = 0
ops = []  # (path, method, operation)
for p, item in paths.items():
    check(isinstance(item, dict), "path %s 不是映射" % p)
    methods = [m for m in item if m in METHODS]
    check(len(methods) >= 1, "path %s 没有任何 operation" % p)
    for m in methods:
        op_count += 1
        ops.append((p, m, item[m]))
        check(bool(item[m].get("responses")), "%s %s 缺少 responses" % (m.upper(), p))

# 4. $ref 可解析
refs = set()


def collect_refs(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref" and isinstance(v, str):
                refs.add(v)
            else:
                collect_refs(v)
    elif isinstance(node, list):
        for x in node:
            collect_refs(x)


collect_refs(doc)


def resolve(ref):
    if not ref.startswith("#/"):
        return None
    cur = doc
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


unresolved = sorted(r for r in refs if resolve(r) is None)
check(not unresolved, "存在无法解析的 $ref：%s" % unresolved)
check(all(r.startswith("#/components/") for r in refs), "存在指向 components 之外的 $ref")

# 5. 必需 schema
schemas = (doc.get("components") or {}).get("schemas") or {}
missing = [n for n in REQUIRED_SCHEMAS if n not in schemas]
check(not missing, "缺少必需 schema：%s" % missing)

# 6. 状态机枚举
for key, expected in EXPECTED.items():
    schema_name, prop = key.split(".")
    actual = (schemas.get(schema_name, {}).get("properties", {}).get(prop) or {}).get("enum")
    check(actual == expected, "%s 枚举不一致：期望 %s，实际 %s" % (key, expected, actual))


# 7/8. 逐 operation 检查幂等头与错误响应
def op_params(op):
    out = []
    for prm in op.get("parameters", []) or []:
        if isinstance(prm, dict) and "$ref" in prm:
            r = resolve(prm["$ref"])
            if isinstance(r, dict):
                out.append(r)
        elif isinstance(prm, dict):
            out.append(prm)
    return out


idem_exempt = 0
idem_checked = 0
for p, m, op in ops:
    is_login = p.endswith("/login")
    is_upload = p == "/attachments" and m == "post"
    is_webhook = p.startswith("/webhooks/")
    need_idem = m in WRITE_METHODS and not is_login and not is_upload and not is_webhook
    names = [x.get("name") for x in op_params(op)]
    if need_idem:
        idem_checked += 1
        check("Idempotency-Key" in names, "%s %s 缺少 Idempotency-Key" % (m.upper(), p))
    elif m in WRITE_METHODS:
        idem_exempt += 1
    for code in ERROR_CODES:
        check(code in op.get("responses", {}), "%s %s 缺少 %s 响应" % (m.upper(), p, code))

# 输出
line_count = sum(1 for _ in open(YAML_PATH, encoding="utf-8"))
print("=" * 68)
print("OpenAPI 校验报告")
print("=" * 68)
print("文件            :", YAML_PATH)
print("openapi         :", doc.get("openapi"))
print("servers[0].url  :", (doc.get("servers") or [{}])[0].get("url"))
print("path 数量       :", path_count)
print("operation 数量  :", op_count)
print("schema 数量     :", len(schemas))
print("$ref 去重数量   :", len(refs), " (无法解析:", len(unresolved), ")")
print("写接口幂等检查  :", idem_checked, " 个需检查,", idem_exempt, " 个豁免")
print("文件行数        :", line_count)
if warnings:
    print("\n警告:")
    for w in warnings:
        print("  -", w)
if errors:
    print("\n结果: FAIL，共 %d 个问题:" % len(errors))
    for e in errors:
        print("  -", e)
    sys.exit(1)
print("\n结果: PASS - 全部检查通过")
