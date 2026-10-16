from tests.conftest import auth, new_key, staff_token


def _first_product(client, token):
    products = client.get("/api/v1/products", headers=auth(token), params={"page_size": 50}).json()
    return products["items"][0]


def test_products_come_from_enterprise_knowledge_base(client):
    token = staff_token(client)
    items = client.get("/api/v1/products", headers=auth(token), params={"page_size": 50}).json()["items"]
    names = {i["name"] for i in items}
    assert "栖云智能门锁 L3 Pro" in names
    assert "栖云摄像头 C2 守望版" in names
    assert "栖云扫地机器人 R5 Max" in names
    assert "栖云智能吸顶灯 LightOne" in names
    assert "栖云家庭网关 Hub G1" in names
    lock = next(i for i in items if i["spu_code"] == "SPU-QL-L3P")
    assert lock["install_required"] is True
    assert "8 节 AA 碱性电池" in str(lock["spec_summary"])
    assert lock["skus"][0]["sellable_qty"] > 0


def test_public_search_only_returns_on_sale(client):
    token = staff_token(client)
    created = client.post("/api/v1/products", headers=auth(token, new_key()), json={
        "spu_code": "SPU-DRAFT-01", "name": "草稿商品", "category_id": 1, "brand_id": 1}).json()
    search = client.get("/api/v1/products/search").json()
    assert all(i["spu_code"] != "SPU-DRAFT-01" for i in search["items"])
    detail = client.get(f"/api/v1/products/{created['id']}/public")
    assert detail.status_code == 404


def test_publish_requires_sku(client):
    token = staff_token(client)
    created = client.post("/api/v1/products", headers=auth(token, new_key()), json={
        "spu_code": "SPU-NOSKU-01", "name": "无SKU商品", "category_id": 1, "brand_id": 1}).json()
    resp = client.post(f"/api/v1/products/{created['id']}/publish", headers=auth(token, new_key()))
    assert resp.status_code == 409
    assert resp.json()["code"] == "PRODUCT_NO_SKU"
    sku = client.post(f"/api/v1/products/{created['id']}/skus", headers=auth(token, new_key()), json={
        "sku_code": "SKU-NOSKU-01", "name": "默认规格", "price": 199.0}).json()
    assert sku["price"] == "199.00"
    published = client.post(f"/api/v1/products/{created['id']}/publish", headers=auth(token, new_key()))
    assert published.status_code == 200 and published.json()["status"] == "ON_SALE"


def test_inventory_adjust_records_ledger_and_blocks_negative(client):
    token = staff_token(client, "stock01")
    stock = client.get("/api/v1/inventory", headers=auth(token), params={"page_size": 1}).json()["items"][0]
    before = stock["qty_available"]
    adjust = client.post("/api/v1/inventory/adjust", headers=auth(token, new_key()), json={
        "sku_id": stock["sku_id"], "warehouse_id": stock["warehouse_id"], "change_type": "PURCHASE_IN",
        "qty_delta": 25, "reason": "采购入库"})
    assert adjust.status_code == 200, adjust.text
    assert adjust.json()["qty_available"] == before + 25
    ledger = client.get("/api/v1/inventory/ledger", headers=auth(token), params={"sku_id": stock["sku_id"]}).json()
    assert ledger["items"][0]["change_type"] == "PURCHASE_IN"
    assert ledger["items"][0]["qty_delta"] == 25
    too_much = client.post("/api/v1/inventory/adjust", headers=auth(token, new_key()), json={
        "sku_id": stock["sku_id"], "warehouse_id": stock["warehouse_id"], "change_type": "DAMAGE",
        "qty_delta": -(before + 1000), "reason": "报损"})
    assert too_much.status_code == 409
    assert too_much.json()["code"] == "INVENTORY_INSUFFICIENT"


def test_inventory_version_conflict(client):
    token = staff_token(client, "stock01")
    stock = client.get("/api/v1/inventory", headers=auth(token), params={"page_size": 1}).json()["items"][0]
    first = client.post("/api/v1/inventory/adjust", headers=auth(token, new_key()), json={
        "sku_id": stock["sku_id"], "warehouse_id": stock["warehouse_id"], "change_type": "ADJUST",
        "qty_delta": 1, "reason": "盘点", "version": stock["version"]}).json()
    stale = client.post("/api/v1/inventory/adjust", headers=auth(token, new_key()), json={
        "sku_id": stock["sku_id"], "warehouse_id": stock["warehouse_id"], "change_type": "ADJUST",
        "qty_delta": 1, "reason": "盘点", "version": stock["version"]})
    assert stale.status_code == 409
    assert stale.json()["code"] == "INVENTORY_VERSION_CONFLICT"
    assert first["version"] == stock["version"] + 1


def test_low_stock_alerts(client):
    token = staff_token(client, "stock01")
    alerts = client.get("/api/v1/inventory/alerts", headers=auth(token)).json()
    assert isinstance(alerts["items"], list) and len(alerts["items"]) >= 1
    assert alerts["meta"]["total"] == alerts["total"]
