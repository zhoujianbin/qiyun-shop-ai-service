from tests.conftest import auth, customer_token, new_key, staff_token
from tests.helpers import create_order, first_purchasable_sku, order_body, pay_mock


def test_idempotent_order_creation_with_same_key(client):
    ctoken = customer_token(client, "buyer_guo")
    sku = first_purchasable_sku(client)["sku"]
    key = new_key()
    body = order_body(client, ctoken, sku_id=sku["id"], quantity=1)
    first_resp = client.post("/api/v1/orders", headers=auth(ctoken, key), json=body)
    assert first_resp.status_code == 200, first_resp.text
    first = first_resp.json()
    second = client.post("/api/v1/orders", headers=auth(ctoken, key), json=body)
    assert second.status_code == 200
    assert second.headers.get("Idempotent-Replay") == "true"
    assert second.json()["order_no"] == first["order_no"]
    orders = client.get("/api/v1/orders", headers=auth(ctoken), params={"page_size": 100}).json()
    assert sum(1 for o in orders["items"] if o["order_no"] == first["order_no"]) == 1


def test_same_key_different_body_conflicts(client):
    ctoken = customer_token(client, "buyer_ma")
    sku = first_purchasable_sku(client)["sku"]
    key = new_key()
    key = new_key()
    body = order_body(client, ctoken, sku_id=sku["id"], quantity=1)
    assert client.post("/api/v1/orders", headers=auth(ctoken, key), json=body).status_code == 200
    conflict = client.post("/api/v1/orders", headers=auth(ctoken, key),
                           json=order_body(client, ctoken, sku_id=sku["id"], quantity=2))
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_write_without_idempotency_key_is_rejected(client):
    ctoken = customer_token(client, "buyer_he")
    sku = first_purchasable_sku(client)["sku"]
    resp = client.post("/api/v1/orders", headers=auth(ctoken),
                       json=order_body(client, ctoken, sku_id=sku["id"], quantity=1))
    assert resp.status_code == 400
    assert resp.json()["code"] == "MISSING_IDEMPOTENCY_KEY"


def test_payment_callback_is_idempotent_and_amount_checked(client):
    ctoken = customer_token(client, "buyer_wu")
    sku = first_purchasable_sku(client)["sku"]
    order = create_order(client, ctoken, sku_id=sku["id"], quantity=1)
    payment = order["payments"][0]
    event = {"event_id": f"EVT-{new_key()}", "payment_no": payment["payment_no"],
             "amount": float(payment["amount"]), "channel_txn_no": f"TXN-{new_key()}"}
    first = client.post("/api/v1/webhooks/payment/mock", json=event)
    assert first.status_code == 200 and first.json()["duplicate"] is False
    assert first.json()["order_status"] == "PAID"
    replay = client.post("/api/v1/webhooks/payment/mock", json=event)
    assert replay.status_code == 200 and replay.json()["duplicate"] is True
    other_event = dict(event, event_id=f"EVT-{new_key()}")
    again = client.post("/api/v1/webhooks/payment/mock", json=other_event)
    assert again.status_code == 200 and again.json()["code"] == "PAYMENT_DUPLICATE_CALLBACK"
    detail = client.get(f"/api/v1/orders/{order['id']}", headers=auth(ctoken)).json()
    assert detail["paid_amount"] == detail["payable_amount"]


def test_payment_callback_amount_mismatch(client):
    ctoken = customer_token(client, "buyer_xu")
    sku = first_purchasable_sku(client)["sku"]
    order = create_order(client, ctoken, sku_id=sku["id"], quantity=1)
    payment = order["payments"][0]
    resp = client.post("/api/v1/webhooks/payment/mock", json={
        "event_id": f"EVT-{new_key()}", "payment_no": payment["payment_no"],
        "amount": float(payment["amount"]) - 1})
    assert resp.status_code == 409 and resp.json()["code"] == "PAYMENT_AMOUNT_MISMATCH"


def test_refund_cannot_exceed_paid_amount(client):
    ctoken = customer_token(client, "buyer_chen")
    atoken = staff_token(client, "aftersales01")
    sku = first_purchasable_sku(client)["sku"]
    order = create_order(client, ctoken, sku_id=sku["id"], quantity=1)
    pay_mock(client, ctoken, order["payments"][0]["id"])
    too_much = client.post("/api/v1/refunds", headers=auth(atoken, new_key()), json={
        "order_id": order["id"], "amount": float(order["payable_amount"]) + 100, "reason": "测试超额退款"})
    assert too_much.status_code == 422
    assert too_much.json()["code"] == "VALIDATION_FAILED"
    ok = client.post("/api/v1/refunds", headers=auth(atoken, new_key()), json={
        "order_id": order["id"], "amount": 10, "reason": "补偿性退款"})
    assert ok.status_code == 200 and ok.json()["status"] == "PENDING"
    executed = client.post(f"/api/v1/refunds/{ok.json()['id']}/execute", headers=auth(atoken, new_key()))
    assert executed.status_code == 200 and executed.json()["status"] == "SUCCESS"
    detail = client.get(f"/api/v1/orders/{order['id']}", headers=auth(ctoken)).json()
    assert detail["payment_status"] == "PARTIAL_REFUNDED"
    assert detail["refunded_amount"] == "10.00"
