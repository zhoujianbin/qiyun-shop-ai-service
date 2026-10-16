from tests.conftest import auth, new_key


def first_purchasable_sku(client, limit: int = 50) -> dict:
    search = client.get("/api/v1/products/search", params={"page_size": limit}).json()
    for item in search["items"]:
        detail = client.get(f"/api/v1/products/{item['id']}/public").json()
        for sku in detail.get("skus", []):
            if sku["sellable_qty"] >= 3:
                return {"product": detail, "sku": sku}
    raise AssertionError("没有可购买的 SKU")


def default_address_id(client, token: str) -> int:
    addresses = client.get("/api/v1/customers/me/addresses", headers=auth(token)).json()
    if not addresses:
        created = client.post("/api/v1/customers/me/addresses", headers=auth(token, new_key()), json={
            "receiver_name": "测试收货人", "receiver_phone": "13900000000", "province": "浙江省",
            "city": "杭州市", "district": "余杭区", "detail": "测试地址 1 号", "is_default": True}).json()
        return created["id"]
    return addresses[0]["id"]


def order_body(client, token: str, *, sku_id: int, quantity: int = 1, channel_account_id: int = 1) -> dict:
    return {
        "items": [{"sku_id": sku_id, "quantity": quantity}],
        "channel_account_id": channel_account_id,
        "address_id": default_address_id(client, token),
    }


def create_order(client, token: str, *, sku_id: int, quantity: int = 1, channel_account_id: int = 1,
                 idem: str | None = None) -> dict:
    resp = client.post("/api/v1/orders", headers=auth(token, idem or new_key()),
                       json=order_body(client, token, sku_id=sku_id, quantity=quantity,
                                       channel_account_id=channel_account_id))
    assert resp.status_code == 200, resp.text
    return resp.json()


def inventory_of(client, staff_token: str, sku_id: int, warehouse_id: int) -> dict:
    rows = client.get("/api/v1/inventory", headers=auth(staff_token),
                      params={"page_size": 100}).json()["items"]
    for row in rows:
        if row["sku_id"] == sku_id and row["warehouse_id"] == warehouse_id:
            return row
    raise AssertionError("未找到库存行")


def pay_mock(client, token: str, payment_id: int) -> dict:
    resp = client.post(f"/api/v1/payments/{payment_id}/mock-succeed", headers=auth(token, new_key()))
    assert resp.status_code == 200, resp.text
    return resp.json()


def warehouse_for(sku: dict, quantity: int = 1) -> int:
    rows = [r for r in sku["inventory"] if r["sellable"] >= quantity]
    rows.sort(key=lambda r: r["warehouse_id"])
    assert rows, "没有满足数量的仓库"
    return rows[0]["warehouse_id"]
