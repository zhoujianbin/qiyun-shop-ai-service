"""前端契约回归：用前端真实的请求体形状调用后端，并断言前端读取的字段存在。

用例形状来自 web/src/types/domain.ts（前端契约类型），用于防止后端字段命名与前端漂移。
"""
import uuid

from tests.conftest import auth, new_key, staff_token

DEV_PASSWORD = "Qiyun@2026#Dev"
MOBILE_ZHANG = "13900000001"


def _customer_login(client):
    resp = client.post("/api/v1/auth/customer/login", json={"mobile": MOBILE_ZHANG, "password": DEV_PASSWORD})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["party"] == "CUSTOMER"
    assert "permissions" in body["user"]
    assert "channel_scope" in body["user"]
    return body["access_token"]


def test_frontend_auth_and_channels(client):
    token = _customer_login(client)
    me = client.get("/api/v1/auth/me", headers=auth(token)).json()
    assert me["customer_id"] and me["display_name"]
    assert isinstance(me["channel_scope"], list)

    channels = client.get("/api/v1/channels")
    assert channels.status_code == 200, channels.text
    rows = channels.json()
    assert rows and any(row["is_default"] for row in rows)

    registered = client.post("/api/v1/auth/customer/register", json={
        "mobile": "13800009999", "password": "NewPass@2026", "sms_code": "000000", "nickname": "前端联调客户"})
    assert registered.status_code == 200, registered.text
    assert registered.json()["user"]["display_name"] == "前端联调客户"


def test_frontend_catalog_shapes(client):
    search = client.get("/api/v1/products/search",
                        params={"product_type": "SMART_LOCK", "page": 1, "page_size": 10})
    assert search.status_code == 200, search.text
    page = search.json()
    assert page["total"] >= 1
    # 前端分页依赖 meta.total
    assert page["meta"]["total"] == page["total"]
    assert page["meta"]["page"] == 1 and page["meta"]["page_size"] == 10
    for item in page["items"]:
        assert item["product_type"] == "SMART_LOCK"
        assert item["category_name"] and item["brand_name"]
        assert isinstance(item["channel_scope"], list)
        assert isinstance(item["attributes"], list)
        assert item["media"] and "is_main" in item["media"][0]
        assert item["skus"] and item["skus"][0]["price"]

    detail = client.get(f"/api/v1/products/{page['items'][0]['id']}/public")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["skus"][0]["sku_code"]
    assert "spec_summary" in detail_body and "install_required" in detail_body


def place_paid_shipped_order(client):
    ctoken = _customer_login(client)
    search = client.get("/api/v1/products/search", params={"page_size": 10}).json()
    sku = next(sku for product in search["items"] for sku in product["skus"] if sku["sellable_qty"] >= 2)

    added = client.post("/api/v1/cart/items", headers=auth(ctoken, new_key()),
                        json={"sku_id": sku["id"], "quantity": 2})
    assert added.status_code == 200, added.text
    cart = added.json()
    assert cart["item_count"] >= 1
    line = next(item for item in cart["items"] if item["sku_id"] == sku["id"])
    assert line["stock_available"] is True
    assert line["product_name"] and line["sku_name"]
    cart_item_id = line["id"]
    cart_quantity = line["quantity"]

    default_channel = client.get("/api/v1/channels").json()[0]["id"]
    address = client.post("/api/v1/customers/me/addresses", headers=auth(ctoken, new_key()), json={
        "receiver_name": "前端联调收货人", "receiver_mobile": "13900008888", "province": "浙江省",
        "city": "杭州市", "district": "余杭区", "detail": "文一西路 100 号", "is_default": True})
    assert address.status_code == 200, address.text
    address_body = address.json()
    assert address_body["receiver_mobile_masked"] == "139****8888"

    created = client.post("/api/v1/orders", headers=auth(ctoken, new_key()), json={
        "channel_account_id": default_channel, "source_mode": "CART", "cart_item_ids": [cart_item_id],
        "address_id": address_body["id"], "buyer_remark": "前端联调下单", "coupon_code": None})
    assert created.status_code == 200, created.text
    order = created.json()
    assert order["receiver_phone_masked"] and order["items"][0]["quantity"] == cart_quantity
    assert order["status"] == "PENDING_PAYMENT"

    timeline = client.get(f"/api/v1/orders/{order['id']}/timeline", headers=auth(ctoken)).json()
    assert timeline["items"][0]["field"] == "status" and timeline["items"][0]["created_at"]

    payment = client.post("/api/v1/payments", headers=auth(ctoken, new_key()), json={
        "order_id": order["id"], "method": "WECHAT_PAY", "return_url": "https://mall.local/pay/return",
        "client_ip": "127.0.0.1"})
    assert payment.status_code == 200, payment.text
    payment_body = payment.json()
    assert payment_body["payment_no"] and payment_body["status"] == "PENDING"

    paid = client.post(f"/api/v1/payments/{payment_body['id']}/mock-succeed", headers=auth(ctoken, new_key()),
                       json={"channel_txn_no": "WX-FRONT-001", "remark": "前端联调"})
    assert paid.status_code == 200, paid.text
    assert paid.json()["order"]["status"] == "PAID"

    atoken = staff_token(client, "ops01")
    detail = client.get(f"/api/v1/orders/{order['id']}", headers=auth(atoken)).json()
    item = detail["items"][0]
    shipped = client.post(f"/api/v1/orders/{order['id']}/ship", headers=auth(atoken, new_key()), json={
        "warehouse_id": item["warehouse_id"], "carrier_code": "SF",
        "tracking_no": f"SF-FRONT-{order['id']}", "package_count": 1,
        "items": [{"order_item_id": item["id"], "quantity": item["quantity"]}], "remark": "前端联调发货"})
    assert shipped.status_code == 200, shipped.text
    shipment = shipped.json()
    assert shipment["carrier_code"] == "SF" and shipment["receiver_phone_masked"]
    assert shipment["items"][0]["sku_id"] == item["sku_id"]

    tracked = client.post(f"/api/v1/shipments/{shipment['id']}/tracking-events", headers=auth(atoken, new_key()), json={
        "event_time": "2026-10-16T10:00:00+08:00", "status": "DELIVERED",
        "description": "已签收", "location": "杭州市"})
    assert tracked.status_code == 200
    assert tracked.json()["tracking_events"][0]["source"] in ("MANUAL", "CARRIER_WEBHOOK")

    carrier_list = client.get("/api/v1/carriers", headers=auth(ctoken)).json()
    assert carrier_list["items"] and carrier_list["items"][0]["code"]

    return {"ctoken": ctoken, "atoken": atoken, "order": order, "item": item}


def test_frontend_after_sales_refund_invoice(client):
    context = place_paid_shipped_order(client)
    ctoken = context["ctoken"]
    atoken = staff_token(client, "aftersales01")
    order, item = context["order"], context["item"]

    application = client.post("/api/v1/after-sales/applications", headers=auth(ctoken, new_key()), json={
        "order_id": order["id"], "order_item_id": item["id"], "type": "REFUND_ONLY",
        "reason_code": "QUALITY_ISSUE", "description": "前端联调售后",
        "evidence_attachment_ids": [], "quantity": 1, "refund_amount": order["payable_amount"]})
    assert application.status_code == 200, application.text
    application_body = application.json()
    assert application_body["refund_amount"] and application_body["applied_at"]
    assert application_body["order_no"] == order["order_no"]

    reviewed = client.post(f"/api/v1/after-sales/applications/{application_body['id']}/review",
                           headers=auth(atoken, new_key()), json={
                               "decision": "APPROVE", "approved_amount": order["payable_amount"],
                               "need_return": False, "remark": "前端联调审核通过"})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "APPROVED"
    assert reviewed.json()["review_remark"] == "前端联调审核通过"

    completed = client.post(f"/api/v1/after-sales/applications/{application_body['id']}/complete",
                            headers=auth(atoken, new_key()),
                            json={"conclusion": "同意退款", "refund_amount": order["payable_amount"]})
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "COMPLETED"
    assert completed.json()["refunds"][0]["status"] == "SUCCESS"

    message = client.post(f"/api/v1/after-sales/applications/{application_body['id']}/messages",
                          headers=auth(ctoken, new_key()),
                          json={"content": "请尽快处理", "attachment_ids": [], "visible_to_customer": True})
    assert message.status_code == 200
    assert message.json()["messages"][0]["sender_type"] == "CUSTOMER"

    # 发票：全额退款后订单不允许开票，因此用另一个已支付订单验证前端形状
    fresh = place_paid_shipped_order(client)
    invoice = client.post("/api/v1/invoices", headers=auth(ctoken, new_key()), json={
        "order_id": fresh["order"]["id"], "type": "ELECTRONIC", "title": "某某科技有限公司",
        "tax_no": "91330100MA2AB1CD3E", "bank_name": "某某银行", "email": "fin@example.com"})
    assert invoice.status_code == 200, invoice.text
    invoice_body = invoice.json()
    assert invoice_body["tax_amount"] is None and invoice_body["issue_type"] == "BLUE"

    issued = client.post(f"/api/v1/invoices/{invoice_body['id']}/issue", headers=auth(atoken, new_key()),
                         json={"invoice_no": "INV-FRONT-0001", "issue_type": "BLUE", "tax_amount": "0.00"})
    assert issued.status_code == 200, issued.text
    assert issued.json()["status"] == "ISSUED" and issued.json()["invoice_no"] == "INV-FRONT-0001"


def test_frontend_reports_staff_inventory_audit(client):
    admin = staff_token(client)
    dashboard = client.get("/api/v1/reports/dashboard", headers=auth(admin), params={"days": 30})
    assert dashboard.status_code == 200
    body = dashboard.json()
    for field in ("generated_at", "gross_sales_amount", "net_sales_amount", "refund_amount", "order_count",
                  "avg_order_value", "new_customers", "low_stock_count", "pending_after_sales_count"):
        assert field in body, field
    daily = client.get("/api/v1/reports/sales/daily", headers=auth(admin), params={"days": 30}).json()
    if daily["items"]:
        assert daily["items"][0]["date"] and daily["items"][0]["gmv"]
    inventory_report = client.get("/api/v1/reports/inventory", headers=auth(admin)).json()
    assert inventory_report["total_available_qty"] >= 0 and "low_stock_count" in inventory_report
    after_sales_report = client.get("/api/v1/reports/after-sales", headers=auth(admin)).json()
    assert after_sales_report["application_count"] >= 0
    assert isinstance(after_sales_report["by_status"], list)

    suffix = uuid.uuid4().hex[:6]
    created = client.post("/api/v1/staff/users", headers=auth(admin, new_key()), json={
        "username": f"fe_{suffix}", "display_name": "前端联调员工", "email": "fe@qiyun.local",
        "phone": "13900007777", "password": "FeStaff@2026", "role_codes": ["ECOMMERCE_OPS"],
        "channel_account_ids": [1, 2]})
    assert created.status_code == 200, created.text
    staff_id = created.json()["id"]
    assert created.json()["phone_masked"] == "139****7777"

    updated = client.patch(f"/api/v1/staff/users/{staff_id}", headers=auth(admin, new_key()),
                           json={"display_name": "前端联调员工-改", "status": "ACTIVE", "version": 0})
    assert updated.status_code == 200, updated.text

    detail = client.get(f"/api/v1/staff/users/{staff_id}", headers=auth(admin))
    assert detail.status_code == 200 and detail.json()["display_name"].endswith("-改")

    roles = client.get(f"/api/v1/staff/users/{staff_id}/roles", headers=auth(admin)).json()
    assert roles["role_codes"] == ["ECOMMERCE_OPS"]
    set_roles = client.put(f"/api/v1/staff/users/{staff_id}/roles", headers=auth(admin, new_key()),
                           json={"role_codes": ["AFTER_SALES"]})
    assert set_roles.status_code == 200

    scopes = client.get(f"/api/v1/staff/users/{staff_id}/channel-scopes", headers=auth(admin)).json()
    assert scopes["channel_account_ids"] == [1, 2]
    set_scopes = client.put(f"/api/v1/staff/users/{staff_id}/channel-scopes", headers=auth(admin, new_key()),
                            json={"channel_account_ids": [1]})
    assert set_scopes.status_code == 200 and set_scopes.json()["channel_account_ids"] == [1]

    stock = client.get("/api/v1/inventory", headers=auth(admin), params={"page_size": 1}).json()["items"][0]
    assert stock["product_name"] and "is_low_stock" in stock
    adjusted = client.post("/api/v1/inventory/adjust", headers=auth(admin, new_key()), json={
        "warehouse_id": stock["warehouse_id"], "sku_id": stock["sku_id"], "change_type": "ADJUST",
        "qty_delta": 3, "expected_version": stock["version"], "reason": "前端联调盘点", "remark": "回归"})
    assert adjusted.status_code == 200, adjusted.text

    logs = client.get("/api/v1/audit-logs", headers=auth(admin), params={"page_size": 5}).json()
    assert logs["items"] and "before_data" in logs["items"][0] and "actor_label" in logs["items"][0]

    channels = client.get("/api/v1/channel-accounts", headers=auth(admin)).json()
    assert channels["items"] and "channel_type" in channels["items"][0]
    brands = client.get("/api/v1/brands", headers=auth(admin)).json()
    assert brands["items"] and brands["items"][0]["code"]
    categories = client.get("/api/v1/categories", headers=auth(admin)).json()
    assert categories and "path" in categories[0]
    updated_category = client.patch(f"/api/v1/categories/{categories[0]['id']}", headers=auth(admin, new_key()),
                                    json={"name": categories[0]["name"], "sort_order": 1})
    assert updated_category.status_code == 200, updated_category.text


def test_frontend_attachment_shape(client):
    ctoken = _customer_login(client)
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    uploaded = client.post("/api/v1/attachments", headers=auth(ctoken),
                           files={"file": ("fe.png", png, "image/png")}, data={"owner_type": "after_sales"})
    assert uploaded.status_code == 200, uploaded.text
    body = uploaded.json()
    assert body["url"] and body["size_bytes"] == len(png) and body["is_public"] is False


def test_list_endpoints_return_items_and_meta(client):
    """前端所有列表页都读 .items / .meta.total，这里逐个锁定形状。"""
    admin = staff_token(client)
    ctoken = _customer_login(client)
    paths = [
        "/api/v1/channel-accounts", "/api/v1/brands", "/api/v1/warehouses", "/api/v1/carriers",
        "/api/v1/roles", "/api/v1/permissions", "/api/v1/inventory/alerts", "/api/v1/staff/users",
        "/api/v1/audit-logs",
    ]
    for path in paths:
        resp = client.get(path, headers=auth(admin))
        assert resp.status_code == 200, (path, resp.text)
        body = resp.json()
        assert isinstance(body, dict) and "items" in body, (path, type(body))
        assert body["meta"]["total"] == body["total"], path

    product_id = client.get("/api/v1/products/search", params={"page_size": 1}).json()["items"][0]["id"]
    skus = client.get(f"/api/v1/products/{product_id}/skus", headers=auth(admin))
    assert skus.status_code == 200, skus.text
    assert skus.json()["items"] and "sku_code" in skus.json()["items"][0]

    order = place_paid_shipped_order(client)
    refund = client.post("/api/v1/refunds", headers=auth(staff_token(client, "aftersales01"), new_key()), json={
        "order_id": order["order"]["id"], "amount": 1.0, "reason": "联调退款", "channel": "ORIGINAL"}).json()
    attempts = client.get(f"/api/v1/refunds/{refund['id']}/attempts", headers=auth(admin))
    assert attempts.status_code == 200, attempts.text
    assert isinstance(attempts.json()["items"], list)


def test_channel_without_platform_code_and_product_update_with_published_at(client):
    """回归：两个既有 500 —— 渠道缺 platform_code、商品已发布时 PATCH。"""
    admin = staff_token(client)
    suffix = uuid.uuid4().hex[:6]
    channel = client.post("/api/v1/channel-accounts", headers=auth(admin, new_key()),
                          json={"code": f"FE{suffix}", "name": "前端联调渠道", "channel_type": "ECOM_FLAGSHIP"})
    assert channel.status_code == 200, channel.text
    assert channel.json()["platform_code"] == f"FE{suffix}"

    product = client.get("/api/v1/products", headers=auth(admin), params={"page_size": 1}).json()["items"][0]
    assert product["published_at"], "用于回归的商品必须有 published_at"
    updated = client.patch(f"/api/v1/products/{product['id']}", headers=auth(admin, new_key()),
                           json={"subtitle": f"回归校验 {suffix}"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["subtitle"] == f"回归校验 {suffix}"



def test_cart_can_be_loaded_without_channel_param(client):
    """回归：前端 cartApi.get({signal}) 不带 channel_account_id，必须回退默认渠道而不是 422。"""
    ctoken = _customer_login(client)
    resp = client.get("/api/v1/cart", headers=auth(ctoken))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body and body["channel_account_id"], body
    with_param = client.get("/api/v1/cart", headers=auth(ctoken),
                            params={"channel_account_id": body["channel_account_id"]})
    assert with_param.status_code == 200 and with_param.json()["id"] == body["id"]
