from tests.conftest import auth, customer_token, new_key, staff_token
from tests.helpers import (create_order, first_purchasable_sku, inventory_of, order_body,
                           pay_mock, warehouse_for)


def test_full_order_lifecycle(client):
    ctoken = customer_token(client)
    stoken = staff_token(client, "stock01")
    otoken = staff_token(client, "ops01")
    atoken = staff_token(client, "aftersales01")
    picked = first_purchasable_sku(client)
    sku = picked["sku"]
    price = float(sku["price"])
    warehouse_id = warehouse_for(sku, 2)
    before = inventory_of(client, stoken, sku["id"], warehouse_id)

    # 1. 下单：锁库存 + 生成支付单
    order = create_order(client, ctoken, sku_id=sku["id"], quantity=2)
    assert order["status"] == "PENDING_PAYMENT"
    assert order["payment_status"] == "UNPAID"
    assert order["payable_amount"] == f"{price * 2:.2f}"
    assert order["items"][0]["warehouse_id"] == warehouse_id
    reserved = inventory_of(client, stoken, sku["id"], warehouse_id)
    assert reserved["qty_available"] == before["qty_available"] - 2
    assert reserved["qty_reserved"] == before["qty_reserved"] + 2
    payment = order["payments"][0]
    assert payment["status"] == "PENDING"

    # 2. 支付（模拟渠道成功）
    paid = pay_mock(client, ctoken, payment["id"])
    assert paid["order"]["status"] == "PAID"
    assert paid["order"]["payment_status"] == "PAID"
    assert pay_mock(client, ctoken, payment["id"])["replay"] is True

    # 3. 发货：出库扣减锁定
    ship = client.post(f"/api/v1/orders/{order['id']}/ship", headers=auth(otoken, new_key()), json={
        "carrier_id": 1, "tracking_no": f"SF{order['id']}0001", "warehouse_id": warehouse_id,
        "items": [{"order_item_id": order["items"][0]["id"], "quantity": 2}]})
    assert ship.status_code == 200, ship.text
    assert ship.json()["status"] == "PENDING"
    after_ship = inventory_of(client, stoken, sku["id"], warehouse_id)
    assert after_ship["qty_available"] == before["qty_available"] - 2
    assert after_ship["qty_reserved"] == before["qty_reserved"]
    detail = client.get(f"/api/v1/orders/{order['id']}", headers=auth(stoken)).json()
    assert detail["status"] == "SHIPPED" and detail["fulfillment_status"] == "SHIPPED"

    # 4. 物流签收 + 客户确认收货
    shipment_id = ship.json()["id"]
    delivered = client.post(f"/api/v1/shipments/{shipment_id}/tracking-events", headers=auth(otoken, new_key()), json={
        "status": "DELIVERED", "description": "快件已签收", "location": "杭州"})
    assert delivered.status_code == 200
    received = client.post(f"/api/v1/orders/{order['id']}/confirm-receipt", headers=auth(ctoken, new_key()))
    assert received.status_code == 200 and received.json()["status"] == "COMPLETED"

    # 5. 售后申请 → 审核 → 完成 → 退款
    application = client.post("/api/v1/after-sales/applications", headers=auth(ctoken, new_key()), json={
        "order_id": order["id"], "type": "REFUND_ONLY", "reason_code": "QUALITY_ISSUE",
        "reason_text": "功能异常", "description": "设备无法正常工作", "expect_amount": price * 2,
        "items": [{"order_item_id": order["items"][0]["id"], "quantity": 2}]})
    assert application.status_code == 200, application.text
    app_id = application.json()["id"]
    reviewed = client.post(f"/api/v1/after-sales/applications/{app_id}/review", headers=auth(atoken, new_key()), json={
        "decision": "APPROVE", "approved_amount": price * 2, "need_return": False, "review_note": "核实属实"})
    assert reviewed.status_code == 200 and reviewed.json()["status"] == "APPROVED"
    completed = client.post(f"/api/v1/after-sales/applications/{app_id}/complete", headers=auth(atoken, new_key()), json={
        "method": "ORIGINAL"})
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "COMPLETED"
    assert completed.json()["refund"]["status"] == "SUCCESS"
    final = client.get(f"/api/v1/orders/{order['id']}", headers=auth(stoken)).json()
    assert final["payment_status"] == "REFUNDED"
    assert final["refunded_amount"] == f"{price * 2:.2f}"
    assert final["status"] == "CLOSED"

    # 6. 时间线可追溯
    timeline = client.get(f"/api/v1/orders/{order['id']}/timeline", headers=auth(stoken)).json()
    fields = {item["field"] for item in timeline["items"]}
    assert {"status", "payment_status", "fulfillment_status"} <= fields


def test_cancel_order_releases_reservation(client):
    ctoken = customer_token(client, "buyer_li")
    stoken = staff_token(client, "stock01")
    picked = first_purchasable_sku(client)
    sku = picked["sku"]
    warehouse_id = warehouse_for(sku, 1)
    before = inventory_of(client, stoken, sku["id"], warehouse_id)
    order = create_order(client, ctoken, sku_id=sku["id"], quantity=1)
    mid = inventory_of(client, stoken, sku["id"], warehouse_id)
    assert mid["qty_reserved"] == before["qty_reserved"] + 1
    cancelled = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=auth(ctoken, new_key()),
                            json={"reason": "不想要了"})
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
    after = inventory_of(client, stoken, sku["id"], warehouse_id)
    assert after["qty_available"] == before["qty_available"]
    assert after["qty_reserved"] == before["qty_reserved"]
    again = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=auth(ctoken, new_key()), json={})
    assert again.status_code == 200 and again.json()["status"] == "CANCELLED"


def test_insufficient_stock_returns_409_and_rolls_back(client):
    ctoken = customer_token(client, "buyer_zhao")
    stoken = staff_token(client, "stock01")
    picked = first_purchasable_sku(client)
    sku = picked["sku"]
    warehouse_id = warehouse_for(sku, 1)
    before = inventory_of(client, stoken, sku["id"], warehouse_id)
    body = order_body(client, ctoken, sku_id=sku["id"], quantity=999)
    resp = client.post("/api/v1/orders", headers=auth(ctoken, new_key()), json=body)
    assert resp.status_code == 409
    assert resp.json()["code"] == "INVENTORY_INSUFFICIENT"
    after = inventory_of(client, stoken, sku["id"], warehouse_id)
    assert after["qty_available"] == before["qty_available"]
    assert after["qty_reserved"] == before["qty_reserved"]


def test_partial_shipment_flow(client):
    ctoken = customer_token(client, "buyer_sun")
    stoken = staff_token(client, "ops01")
    picked = first_purchasable_sku(client)
    sku = picked["sku"]
    warehouse_id = warehouse_for(sku, 1)
    order = create_order(client, ctoken, sku_id=sku["id"], quantity=2)
    pay_mock(client, ctoken, order["payments"][0]["id"])
    partial = client.post(f"/api/v1/orders/{order['id']}/ship", headers=auth(stoken, new_key()), json={
        "carrier_id": 2, "tracking_no": f"JD{order['id']}0002", "warehouse_id": warehouse_id,
        "items": [{"order_item_id": order["items"][0]["id"], "quantity": 1}]})
    assert partial.status_code == 200, partial.text
    detail = client.get(f"/api/v1/orders/{order['id']}", headers=auth(stoken)).json()
    assert detail["fulfillment_status"] == "PARTIAL_SHIPPED"
    assert detail["items"][0]["shipped_quantity"] == 1
    over = client.post(f"/api/v1/orders/{order['id']}/ship", headers=auth(stoken, new_key()), json={
        "carrier_id": 2, "tracking_no": f"JD{order['id']}0003", "warehouse_id": warehouse_id,
        "items": [{"order_item_id": order["items"][0]["id"], "quantity": 5}]})
    assert over.status_code == 422


def test_shipped_order_cannot_be_cancelled_or_edited(client):
    ctoken = customer_token(client, "buyer_zhou")
    stoken = staff_token(client, "ops01")
    picked = first_purchasable_sku(client)
    sku = picked["sku"]
    warehouse_id = warehouse_for(sku, 1)
    order = create_order(client, ctoken, sku_id=sku["id"], quantity=1)
    pay_mock(client, ctoken, order["payments"][0]["id"])
    client.post(f"/api/v1/orders/{order['id']}/ship", headers=auth(stoken, new_key()), json={
        "carrier_id": 1, "tracking_no": f"SF{order['id']}0009", "warehouse_id": warehouse_id,
        "items": [{"order_item_id": order["items"][0]["id"], "quantity": 1}]})
    cancel = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=auth(ctoken, new_key()), json={})
    assert cancel.status_code == 409 and cancel.json()["code"] == "ORDER_STATE_INVALID"
    address = client.patch(f"/api/v1/orders/{order['id']}/address", headers=auth(ctoken, new_key()),
                           json={"detail": "新地址"})
    assert address.status_code == 409
