"""四期工具注册表：9 个工具的单一定义处（代码即真源，不建注册表）。

约束（见 design D3/D9）：
- 每个工具给严格 JSON Schema（additionalProperties=false），参数一律视为不可信输入。
- 调用者身份只来自会话 actor，绝不来自工具参数。
- 写工具 run 为空：由 action 服务生成待确认动作，不在此直接执行。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import NotFound, ValidationError
from app.models.generated import Order
from app.services import aftersales, catalog, fulfillment, invoice, knowledge_retrieval, order, payment

TOP_K_DEFAULT = 5


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    run: Callable[[Session, dict, dict], dict] | None
    read_only: bool = True
    requires_identity: bool = False
    scope: str = "knowledge"
    requires_confirm: bool = False


# ---------------------------------------------------------------- 参数校验
def validate_args(spec: ToolSpec, args: dict | None) -> dict:
    """严格校验：多余字段直接拒绝，缺必填拒绝，类型不符拒绝。"""
    schema = spec.input_schema or {}
    properties: dict = schema.get("properties") or {}
    required: list[str] = schema.get("required") or []
    raw = args or {}
    if not isinstance(raw, dict):
        raise ValidationError(f"{spec.name} 参数必须是对象")
    extra = sorted(set(raw) - set(properties))
    if extra and schema.get("additionalProperties") is False:
        raise ValidationError(f"{spec.name} 不接受参数：{', '.join(extra)}")
    missing = [key for key in required if raw.get(key) in (None, "")]
    if missing:
        raise ValidationError(f"{spec.name} 缺少必填参数：{', '.join(missing)}")
    cleaned: dict = {}
    for key, value in raw.items():
        if value is None:
            continue
        expected = (properties.get(key) or {}).get("type")
        if expected == "string" and not isinstance(value, str):
            raise ValidationError(f"{spec.name}.{key} 必须是字符串")
        if expected == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValidationError(f"{spec.name}.{key} 必须是整数")
        allowed = (properties.get(key) or {}).get("enum")
        if allowed and value not in allowed:
            raise ValidationError(f"{spec.name}.{key} 只能是 {allowed} 之一")
        cleaned[key] = value
    return cleaned


def resolve_order(db: Session, actor: dict, order_no: str) -> Order:
    """按订单号取订单；客户/游客只能取到自己的单，取不到一律"没有找到"。"""
    stmt = select(Order).where(Order.tenant_id == settings.tenant_id, Order.order_no == (order_no or "").strip())
    if (actor or {}).get("party") in ("CUSTOMER", "GUEST"):
        stmt = stmt.where(Order.customer_id == actor.get("customer_id"))
    found = db.execute(stmt).scalar_one_or_none()
    if found is None:
        raise NotFound("没有找到该订单")
    return found


# ---------------------------------------------------------------- 只读执行体
def _search_knowledge(db: Session, state: dict, args: dict) -> dict:
    result = knowledge_retrieval.search(
        db, args.get("query") or state.get("question") or "",
        top_k=args.get("top_k") or TOP_K_DEFAULT, actor=args.get("actor"),
        identity_level=args.get("identity_level", "public"),
        filters=args.get("filters") or None,
    )
    return {"hits": result["hits"], "latency_ms": result["debug"]["latency_ms"]}


def _query_product(db: Session, state: dict, args: dict) -> dict:
    model_code = args.get("model_code")
    keyword = args.get("keyword") or model_code
    page = catalog.search_products(db, keyword=keyword, page=1, page_size=3)
    items = [{
        "name": item.get("name"), "model_code": item.get("model_code"),
        "product_line": item.get("product_line"), "price_range": item.get("price_range"),
        "status": item.get("status"),
    } for item in page["items"]]
    return {"facts": {"products": items, "total": page["total"]},
            "note": "价格区间来自商品主档，具体以结算页为准"}


def _query_order(db: Session, state: dict, args: dict) -> dict:
    found = resolve_order(db, state["actor"], args["order_no"])
    view = order.get_order(db, state["actor"], found.id)
    return {"facts": {key: view.get(key) for key in
                      ("order_no", "status", "paid_amount", "created_at", "fulfillment_status")},
            "order_id": found.id}


def _query_shipment(db: Session, state: dict, args: dict) -> dict:
    found = resolve_order(db, state["actor"], args["order_no"])
    page = fulfillment.list_shipments(db, state["actor"], page=1, page_size=50)
    rows = [item for item in page["items"] if item.get("order_id") == found.id]
    facts = [{"shipment_no": row.get("shipment_no"), "status": row.get("status"),
              "carrier_name": row.get("carrier_name"), "tracking_no": row.get("tracking_no"),
              "shipped_at": row.get("shipped_at"), "delivered_at": row.get("delivered_at")}
             for row in rows[:5]]
    return {"facts": {"shipments": facts, "count": len(facts)}, "order_id": found.id}


def _query_payment(db: Session, state: dict, args: dict) -> dict:
    found = resolve_order(db, state["actor"], args["order_no"])
    page = payment.list_payments(db, state["actor"], page=1, page_size=50)
    rows = [item for item in page["items"] if item.get("order_id") == found.id]
    facts = [{"payment_no": row.get("payment_no"), "status": row.get("status"),
              "amount": row.get("amount"), "method": row.get("method"), "paid_at": row.get("paid_at")}
             for row in rows[:5]]
    return {"facts": {"payments": facts, "count": len(facts)}, "order_id": found.id}


def _query_after_sales(db: Session, state: dict, args: dict) -> dict:
    found = resolve_order(db, state["actor"], args["order_no"])
    page = aftersales.list_applications(db, state["actor"], page=1, page_size=50)
    rows = [item for item in page["items"] if item.get("order_id") == found.id]
    facts = [{"application_no": row.get("application_no"), "type": row.get("type"),
              "status": row.get("status"), "applied_at": row.get("applied_at")}
             for row in rows[:5]]
    return {"facts": {"after_sales": facts, "count": len(facts)}, "order_id": found.id}


def _query_invoice(db: Session, state: dict, args: dict) -> dict:
    found = resolve_order(db, state["actor"], args["order_no"])
    page = invoice.list_invoices(db, state["actor"], page=1, page_size=50)
    rows = [item for item in page["items"] if item.get("order_id") == found.id]
    facts = [{"invoice_no": row.get("invoice_no"), "status": row.get("status"),
              "type": row.get("type"), "amount": row.get("amount")} for row in rows[:5]]
    return {"facts": {"invoices": facts, "count": len(facts)}, "order_id": found.id}


MY_ORDERS_SCAN_LIMIT = 10


def _query_my_orders(db: Session, state: dict, args: dict) -> dict:
    """列调用者本人的订单，可按商品名/状态过滤。

    一期 list_orders 的 keyword 只匹配单号与收件人，所以这里先取最近 N 单，
    再逐单取明细、在进程内按商品名过滤（N≤10，实测单次 <5ms）。
    """
    actor = state["actor"] or {}
    try:
        limit = int(args.get("limit") or 5)
    except (TypeError, ValueError):
        limit = 5
    limit = max(1, min(limit, MY_ORDERS_SCAN_LIMIT))
    status = args.get("status")
    keyword = (args.get("product_keyword") or "").strip()

    page = order.list_orders(db, actor, page=1, page_size=MY_ORDERS_SCAN_LIMIT,
                             status=status)
    matched: list[dict] = []
    for item in page["items"]:
        detail = order.get_order(db, actor, item["id"])
        lines = detail.get("items") or []
        names = [str(line.get("product_name") or "") for line in lines]
        if keyword and not any(keyword in name for name in names):
            continue
        matched.append({
            "order_no": detail.get("order_no"),
            "status": detail.get("status"),
            "created_at": detail.get("created_at"),
            "paid_amount": detail.get("paid_amount"),
            "items": [{"product_name": line.get("product_name"),
                       "quantity": line.get("quantity"),
                       "after_sales_status": line.get("after_sales_status")}
                      for line in lines],
        })
        if len(matched) >= limit:
            break
    return {"facts": {"orders": matched, "matched": len(matched),
                      "scanned": len(page["items"]), "total_orders": page["total"],
                      "keyword": keyword or None},
            "note": "这是调用者本人的订单摘要，明细与写操作仍需按订单单独核验"}


def _order_selector(desc: str) -> dict:
    return {"type": "object",
            "properties": {"order_no": {"type": "string",
                                        "description": desc}},
            "required": ["order_no"], "additionalProperties": False}


ORDER_NO_HINT = "形如 SO2026... 的订单号；只在用户明确给出时填，禁止编造"


TOOLS: dict[str, ToolSpec] = {
    "search_knowledge": ToolSpec(
        name="search_knowledge",
        description=("当问题属于产品使用、政策口径、故障排查等知识类问题时使用。"
                     "用户问具体订单/物流/支付等实时事实时不要用它，改用订单类工具。"),
        input_schema={"type": "object",
                      "properties": {"query": {"type": "string", "description": "检索词"},
                                     "top_k": {"type": "integer", "description": "返回条数，默认 5"}},
                      "required": ["query"], "additionalProperties": False},
        run=_search_knowledge, read_only=True, requires_identity=False, scope="knowledge"),
    "query_product": ToolSpec(
        name="query_product",
        description=("当用户询问在售商品、型号、价格区间或参数时使用。"
                     "用户问订单状态、物流或售后时不要用。"),
        input_schema={"type": "object",
                      "properties": {"keyword": {"type": "string", "description": "商品名称或关键词"},
                                     "model_code": {"type": "string", "description": "形如 QL-L3P 的型号"}},
                      "additionalProperties": False},
        run=_query_product, read_only=True, requires_identity=False, scope="catalog"),
    "query_my_orders": ToolSpec(
        name="query_my_orders",
        description=("当用户提到自己的订单但没给订单号（例如“我订单里那个门锁”）时，"
                     "先用它列出本人订单，可按商品名或状态过滤。"
                     "用户已给出订单号时不要用，直接查该单。"),
        input_schema={"type": "object",
                      "properties": {
                          "product_keyword": {"type": "string",
                                              "description": "商品名关键词，如 门锁、摄像头、扫地机"},
                          "status": {"type": "string",
                                     "description": "订单状态，如 PENDING_PAYMENT、COMPLETED"},
                          "limit": {"type": "integer",
                                    "description": "最多返回几单，1-10，默认 5"},
                      },
                      "additionalProperties": False},
        run=_query_my_orders, read_only=True, requires_identity=False, scope="order"),
    "query_order": ToolSpec(
        name="query_order",
        description=("当用户给出订单号并询问订单状态、金额、下单时间等订单事实时使用。"
                     "用户只问怎么查订单且未给订单号时不要调用，先反问。"),
        input_schema=_order_selector(ORDER_NO_HINT),
        run=_query_order, read_only=True, requires_identity=True, scope="order"),
    "query_shipment": ToolSpec(
        name="query_shipment",
        description=("当用户给出订单号并询问物流、快递、到货进度时使用。"
                     "用户问的是退款或售后进度时不要用，改用 query_after_sales。"),
        input_schema=_order_selector(ORDER_NO_HINT),
        run=_query_shipment, read_only=True, requires_identity=True, scope="fulfillment"),
    "query_payment": ToolSpec(
        name="query_payment",
        description=("当用户给出订单号并询问支付是否成功、扣款金额、支付方式时使用。"
                     "用户询问退款到账时不要用，退款进度用 query_after_sales。"),
        input_schema=_order_selector(ORDER_NO_HINT),
        run=_query_payment, read_only=True, requires_identity=True, scope="payment"),
    "query_after_sales": ToolSpec(
        name="query_after_sales",
        description=("当用户给出订单号并询问退换货、维修、退款进度时使用。"
                     "用户只是问退货政策时用 search_knowledge，不要调用本工具。"),
        input_schema=_order_selector(ORDER_NO_HINT),
        run=_query_after_sales, read_only=True, requires_identity=True, scope="aftersales"),
    "query_invoice": ToolSpec(
        name="query_invoice",
        description=("当用户给出订单号并询问发票是否已开好、发票类型或金额时使用。"
                     "用户询问如何申请发票时不要用本工具，改用 search_knowledge。"),
        input_schema=_order_selector(ORDER_NO_HINT),
        run=_query_invoice, read_only=True, requires_identity=True, scope="invoice"),
    "cancel_order": ToolSpec(
        name="cancel_order",
        description=("当用户明确要求取消订单且已给出订单号时使用。"
                     "订单已发货或已完成时不要调用，引导走退货退款流程。"
                     "调用本工具只生成待确认动作，不直接改单。"),
        input_schema={"type": "object",
                      "properties": {"order_no": {"type": "string", "description": ORDER_NO_HINT},
                                     "reason": {"type": "string", "description": "用户给出的取消原因"}},
                      "required": ["order_no"], "additionalProperties": False},
        run=None, read_only=False, requires_identity=True, scope="order", requires_confirm=True),
    "create_after_sales": ToolSpec(
        name="create_after_sales",
        description=("当用户明确要求申请退换货或维修且已给出订单号时使用。"
                     "用户只是咨询政策时不要调用。"
                     "调用本工具只生成待确认动作，不直接改单，且提交后不可撤销。"),
        input_schema={"type": "object",
                      "properties": {
                          "order_no": {"type": "string", "description": ORDER_NO_HINT},
                          "type": {"type": "string", "description": "售后类型",
                                   "enum": list(aftersales.TYPES)},
                          "reason_code": {"type": "string", "description": "问题原因编码"},
                          "description": {"type": "string", "description": "用户描述的问题"},
                          "quantity": {"type": "integer", "description": "数量，默认 1"},
                      },
                      "required": ["order_no", "type", "reason_code"], "additionalProperties": False},
        run=None, read_only=False, requires_identity=True, scope="aftersales", requires_confirm=True),
}


def llm_tools(*, include_write: bool = True, allowed: set[str] | None = None) -> list[dict]:
    """给模型看的工具清单：只有 name/description/input_schema，没有实现细节。"""
    schemas = []
    for spec in TOOLS.values():
        if not include_write and not spec.read_only:
            continue
        if allowed is not None and spec.name not in allowed:
            continue
        schemas.append({"type": "function",
                        "function": {"name": spec.name, "description": spec.description,
                                     "parameters": spec.input_schema}})
    return schemas


def read_tool_names() -> set[str]:
    return {spec.name for spec in TOOLS.values() if spec.read_only}


def parse_arguments(raw: str | None) -> dict:
    """模型给的 arguments 是字符串，必须解析后再校验。"""
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValidationError("工具参数不是合法 JSON") from exc
    if not isinstance(value, dict):
        raise ValidationError("工具参数必须是对象")
    return value
