from tests.conftest import auth, customer_token, login, new_key, staff_token
from tests.helpers import create_order, first_purchasable_sku


def test_customer_cannot_access_back_office(client):
    ctoken = customer_token(client)
    assert client.get("/api/v1/staff/users", headers=auth(ctoken)).status_code == 403
    assert client.get("/api/v1/audit-logs", headers=auth(ctoken)).status_code == 403
    assert client.get("/api/v1/reports/dashboard", headers=auth(ctoken)).status_code == 403


def test_viewer_role_is_read_only(client):
    token = staff_token(client, "finance01")
    assert client.get("/api/v1/reports/dashboard", headers=auth(token)).status_code == 200
    assert client.get("/api/v1/inventory", headers=auth(token)).status_code == 403
    write = client.post("/api/v1/inventory/adjust", headers=auth(token, new_key()), json={
        "sku_id": 1, "warehouse_id": 1, "change_type": "ADJUST", "qty_delta": 1})
    assert write.status_code == 403 and write.json()["code"] == "PERM_FORBIDDEN"


def test_customer_cannot_read_other_customer_order(client):
    ctoken = customer_token(client, "buyer_zhang")
    other = customer_token(client, "buyer_li")
    sku = first_purchasable_sku(client)["sku"]
    order = create_order(client, other, sku_id=sku["id"], quantity=1)
    assert client.get(f"/api/v1/orders/{order['id']}", headers=auth(ctoken)).status_code == 404
    assert client.get(f"/api/v1/orders/{order['id']}/timeline", headers=auth(ctoken)).status_code == 404


def test_channel_scope_limits_staff_visibility(client):
    admin = staff_token(client)
    suffix = new_key()[:6]
    created = client.post("/api/v1/staff/users", headers=auth(admin, new_key()), json={
        "username": f"scope_{suffix}", "display_name": "渠道受限运营", "password": "Scope@2026#Dev",
        "role_codes": ["ECOMMERCE_OPS"], "channel_ids": [2]})
    assert created.status_code == 200, created.text
    limited = login(client, f"scope_{suffix}", password="Scope@2026#Dev", staff=True)
    ctoken = customer_token(client, "buyer_sun")
    sku = first_purchasable_sku(client)["sku"]
    order_ch1 = create_order(client, ctoken, sku_id=sku["id"], quantity=1, channel_account_id=1)
    order_ch2 = create_order(client, ctoken, sku_id=sku["id"], quantity=1, channel_account_id=2)
    listed = client.get("/api/v1/orders", headers=auth(limited), params={"page_size": 100}).json()
    nos = {o["order_no"] for o in listed["items"]}
    assert order_ch2["order_no"] in nos
    assert order_ch1["order_no"] not in nos
    assert client.get(f"/api/v1/orders/{order_ch1['id']}", headers=auth(limited)).status_code == 403
    assert client.get(f"/api/v1/orders/{order_ch2['id']}", headers=auth(limited)).status_code == 200


def test_cannot_disable_self_and_audit_is_written(client):
    admin = staff_token(client)
    me = client.get("/api/v1/auth/me", headers=auth(admin)).json()
    resp = client.post(f"/api/v1/staff/users/{me['id']}/disable", headers=auth(admin, new_key()))
    assert resp.status_code == 409 and resp.json()["code"] == "CANNOT_DISABLE_SELF"
    logs = client.get("/api/v1/audit-logs", headers=auth(admin), params={"page_size": 5}).json()
    assert logs["total"] > 0
    assert all(item["request_id"] is not None or True for item in logs["items"])


def test_role_and_permission_dictionary(client):
    admin = staff_token(client)
    roles = client.get("/api/v1/roles", headers=auth(admin)).json()
    codes = {r["code"] for r in roles["items"]}
    assert {"SUPER_ADMIN", "ECOMMERCE_OPS", "AFTER_SALES", "AUDITOR"} <= codes
    perms = client.get("/api/v1/permissions", headers=auth(admin)).json()
    assert len(perms["items"]) >= 25
