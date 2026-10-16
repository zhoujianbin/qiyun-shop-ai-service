from tests.conftest import auth, customer_token, new_key, staff_token
from tests.helpers import create_order, first_purchasable_sku, pay_mock


def test_return_refund_requires_return_shipment(client):
    ctoken = customer_token(client, "buyer_zhang")
    atoken = staff_token(client, "aftersales01")
    sku = first_purchasable_sku(client)["sku"]
    order = create_order(client, ctoken, sku_id=sku["id"], quantity=1)
    pay_mock(client, ctoken, order["payments"][0]["id"])
    app = client.post("/api/v1/after-sales/applications", headers=auth(ctoken, new_key()), json={
        "order_id": order["id"], "type": "RETURN_REFUND", "reason_code": "DAMAGE_ON_ARRIVAL",
        "reason_text": "到货破损", "expect_amount": float(order["payable_amount"]),
        "items": [{"order_item_id": order["items"][0]["id"], "quantity": 1}]}).json()
    assert app["status"] == "SUBMITTED" and app["need_return"] is True
    reviewed = client.post(f"/api/v1/after-sales/applications/{app['id']}/review", headers=auth(atoken, new_key()), json={
        "decision": "APPROVE", "approved_amount": float(order["payable_amount"]), "need_return": True}).json()
    assert reviewed["status"] == "WAITING_RETURN"
    premature = client.post(f"/api/v1/after-sales/applications/{app['id']}/complete", headers=auth(atoken, new_key()), json={})
    assert premature.status_code == 409
    assert premature.json()["code"] == "AFTER_SALES_STATE_INVALID"
    shipped = client.post(f"/api/v1/after-sales/applications/{app['id']}/return-shipment",
                          headers=auth(ctoken, new_key()), json={"carrier_id": 1, "tracking_no": "SF-RETURN-0001"})
    assert shipped.status_code == 200 and shipped.json()["status"] == "RETURN_SHIPPED"
    received = client.post(f"/api/v1/after-sales/applications/{app['id']}/receive",
                           headers=auth(atoken, new_key()), json={"restock": True})
    assert received.status_code == 200 and received.json()["status"] == "RECEIVED"
    rf = client.post("/api/v1/refunds", headers=auth(atoken, new_key()), json={
        "order_id": order["id"], "application_id": app["id"], "amount": float(order["payable_amount"])}).json()
    executed = client.post(f"/api/v1/refunds/{rf['id']}/execute", headers=auth(atoken, new_key())).json()
    assert executed["status"] == "SUCCESS"
    detail = client.get(f"/api/v1/after-sales/applications/{app['id']}", headers=auth(atoken)).json()
    assert detail["messages"][0]["author_type"] == "CUSTOMER"
    assert len(detail["refunds"]) == 1


def test_reject_and_cancel_after_sales(client):
    ctoken = customer_token(client, "buyer_li")
    atoken = staff_token(client, "aftersales02")
    sku = first_purchasable_sku(client)["sku"]
    order = create_order(client, ctoken, sku_id=sku["id"], quantity=1)
    pay_mock(client, ctoken, order["payments"][0]["id"])
    app = client.post("/api/v1/after-sales/applications", headers=auth(ctoken, new_key()), json={
        "order_id": order["id"], "type": "REFUND_ONLY", "reason_code": "NOT_AS_DESCRIBED",
        "expect_amount": 20.0, "items": [{"order_item_id": order["items"][0]["id"], "quantity": 1}]}).json()
    rejected = client.post(f"/api/v1/after-sales/applications/{app['id']}/review", headers=auth(atoken, new_key()), json={
        "decision": "REJECT", "review_note": "不符合退款条件"}).json()
    assert rejected["status"] == "REJECTED"
    detail = client.get(f"/api/v1/orders/{order['id']}", headers=auth(ctoken)).json()
    assert detail["after_sales_status"] == "REJECTED"
    second = client.post("/api/v1/after-sales/applications", headers=auth(ctoken, new_key()), json={
        "order_id": order["id"], "type": "REFUND_ONLY", "reason_code": "QUALITY_ISSUE",
        "expect_amount": 20.0, "items": [{"order_item_id": order["items"][0]["id"], "quantity": 1}]}).json()
    cancelled = client.post(f"/api/v1/after-sales/applications/{second['id']}/cancel",
                            headers=auth(ctoken, new_key()), json={"reason": "问题已解决"}).json()
    assert cancelled["status"] == "CANCELLED"


def test_invoice_rules(client):
    ctoken = customer_token(client, "buyer_wang")
    ftoken = staff_token(client, "finance01")
    atoken = staff_token(client, "aftersales01")
    sku = first_purchasable_sku(client)["sku"]
    order = create_order(client, ctoken, sku_id=sku["id"], quantity=1)
    pay_mock(client, ctoken, order["payments"][0]["id"])
    bad = client.post("/api/v1/invoices", headers=auth(ctoken, new_key()), json={
        "order_id": order["id"], "title_type": "COMPANY", "title": "某某公司", "tax_no": "123"})
    assert bad.status_code == 422
    invoice = client.post("/api/v1/invoices", headers=auth(ctoken, new_key()), json={
        "order_id": order["id"], "title_type": "COMPANY", "title": "某某科技有限公司",
        "tax_no": "91330100MA2AB1CD3E"}).json()
    assert invoice["status"] == "REQUESTED"
    write_forbidden = client.post(f"/api/v1/invoices/{invoice['id']}/issue", headers=auth(ftoken, new_key()), json={})
    assert write_forbidden.status_code == 403
    issued = client.post(f"/api/v1/invoices/{invoice['id']}/issue", headers=auth(atoken, new_key()), json={}).json()
    assert issued["status"] == "ISSUED" and issued["invoice_no"]
    assert issued["file_url"]


def test_reports_and_audit_for_admin(client):
    admin = staff_token(client)
    dashboard = client.get("/api/v1/reports/dashboard", headers=auth(admin), params={"days": 30})
    assert dashboard.status_code == 200
    body = dashboard.json()
    for key in ("order_count", "paid_order_count", "gmv", "paid_amount", "refunded_amount", "net_revenue",
                "low_stock_count", "pending_after_sales", "product_count", "sku_count"):
        assert key in body
    daily = client.get("/api/v1/reports/sales/daily", headers=auth(admin), params={"days": 30}).json()
    assert "items" in daily
    inv = client.get("/api/v1/reports/inventory", headers=auth(admin)).json()
    assert inv["total_available"] >= 0 and "alerts" in inv
    after = client.get("/api/v1/reports/after-sales", headers=auth(admin)).json()
    assert "by_status" in after and "refund_count" in after
    logs = client.get("/api/v1/audit-logs", headers=auth(admin), params={"page_size": 20}).json()
    actions = {i["action"] for i in logs["items"]}
    assert actions, "审计日志不应为空"


def test_cart_flow(client):
    ctoken = customer_token(client, "buyer_ma")
    sku = first_purchasable_sku(client)["sku"]
    added = client.post("/api/v1/cart/items", headers=auth(ctoken, new_key()), json={
        "sku_id": sku["id"], "quantity": 2, "channel_account_id": 1})
    assert added.status_code == 200 and added.json()["items"][0]["quantity"] == 2
    assert added.json()["total_amount"] == f"{float(sku['price']) * 2:.2f}"
    item_id = added.json()["items"][0]["id"]
    updated = client.patch(f"/api/v1/cart/items/{item_id}", headers=auth(ctoken, new_key()), json={"quantity": 3})
    assert updated.json()["items"][0]["quantity"] == 3
    cart = client.get("/api/v1/cart", headers=auth(ctoken), params={"channel_account_id": 1}).json()
    assert cart["items"][0]["available"] in (True, False)
    removed = client.delete(f"/api/v1/cart/items/{item_id}", headers=auth(ctoken, new_key()))
    assert removed.status_code == 200 and removed.json()["items"] == []
