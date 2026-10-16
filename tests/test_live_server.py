"""真实 HTTP 端到端测试：启动 uvicorn 子进程，通过真实网络完成下单到收货全流程。"""
import os
import re
import socket
import subprocess
import sys
import time
import pathlib
import uuid

import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEV_PASSWORD = "Qiyun@2026#Dev"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def live_server():
    port = _free_port()
    env = dict(os.environ)
    env.setdefault("LOG_LEVEL", "ERROR")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "error"],
        cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    base = f"http://127.0.0.1:{port}"
    client = httpx.Client(base_url=base, timeout=20.0)
    for _ in range(60):
        if proc.poll() is not None:
            raise AssertionError("uvicorn 启动失败：" + (proc.stdout.read() if proc.stdout else ""))
        try:
            if client.get("/api/v1/system/health").status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.5)
    else:
        proc.terminate()
        raise AssertionError("uvicorn 未在超时内就绪")
    yield client
    client.close()
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def _auth(token: str, idem: bool = False) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    if idem:
        headers["Idempotency-Key"] = uuid.uuid4().hex
    return headers


def test_live_order_flow_over_http(live_server: httpx.Client):
    client = live_server
    staff = client.post("/api/v1/auth/staff/login", json={"username": "admin", "password": DEV_PASSWORD}).json()
    customer = client.post("/api/v1/auth/customer/login", json={"username": "buyer_zhang", "password": DEV_PASSWORD}).json()
    ctoken, stoken = customer["access_token"], staff["access_token"]

    address = client.get("/api/v1/customers/me/addresses", headers=_auth(ctoken)).json()[0]
    search = client.get("/api/v1/products/search", params={"page_size": 5}).json()
    sku = None
    for item in search["items"]:
        detail = client.get(f"/api/v1/products/{item['id']}/public").json()
        for candidate in detail["skus"]:
            if candidate["sellable_qty"] >= 1:
                sku = candidate
                break
        if sku:
            break
    assert sku, "没有可售 SKU"

    created = client.post("/api/v1/orders", headers=_auth(ctoken, True), json={
        "items": [{"sku_id": sku["id"], "quantity": 1}],
        "channel_account_id": 1,
        "address_id": address["id"],
    })
    assert created.status_code == 200, created.text
    order = created.json()
    assert order["status"] == "PENDING_PAYMENT"
    order_no = order["order_no"]

    replay = client.post("/api/v1/orders", headers=_auth(ctoken, True), json={
        "items": [{"sku_id": sku["id"], "quantity": 1}],
        "channel_account_id": 1,
        "address_id": address["id"],
    })
    assert replay.status_code == 200 and replay.json()["order_no"] != order_no

    payment = order["payments"][0]
    paid = client.post(f"/api/v1/payments/{payment['id']}/mock-succeed", headers=_auth(ctoken, True))
    assert paid.status_code == 200 and paid.json()["order"]["status"] == "PAID"

    ship = client.post(f"/api/v1/orders/{order['id']}/ship", headers=_auth(stoken, True), json={
        "carrier_id": 1, "tracking_no": f"SF-LIVE-{order['id']}", "warehouse_id": order["items"][0]["warehouse_id"],
        "items": [{"order_item_id": order["items"][0]["id"], "quantity": 1}],
    })
    assert ship.status_code == 200, ship.text
    shipment_id = ship.json()["id"]

    tracked = client.post(f"/api/v1/shipments/{shipment_id}/tracking-events", headers=_auth(stoken, True), json={
        "status": "DELIVERED", "description": "快件已签收", "location": "杭州"})
    assert tracked.status_code == 200

    received = client.post(f"/api/v1/orders/{order['id']}/confirm-receipt", headers=_auth(ctoken, True))
    assert received.status_code == 200 and received.json()["status"] == "COMPLETED"

    detail = client.get(f"/api/v1/orders/{order['id']}", headers=_auth(ctoken)).json()
    assert detail["payment_status"] == "PAID" and detail["fulfillment_status"] == "DELIVERED"

    dashboard = client.get("/api/v1/reports/dashboard", headers=_auth(stoken)).json()
    assert dashboard["order_count"] >= 1 and float(dashboard["paid_amount"]) > 0

    logs = client.get("/api/v1/audit-logs", headers=_auth(stoken), params={"page_size": 5}).json()
    assert logs["total"] > 0


def test_live_spa_assets_or_skip(live_server: httpx.Client):
    dist = ROOT / "web" / "dist"
    if not dist.is_dir():
        pytest.skip("前端构建产物不存在，跳过 SPA 挂载校验")
    index = (dist / "index.html").read_text(encoding="utf-8")
    assert "<div id=" in index

    root = live_server.get("/")
    assert root.status_code == 200
    assert "text/html" in root.headers.get("content-type", "")

    match = re.search(r'src="(/assets/[^"]+)"', index)
    assert match, "index.html 未引用构建后的 JS"
    asset = live_server.get(match.group(1))
    assert asset.status_code == 200
    assert "javascript" in asset.headers.get("content-type", "")
    assert len(asset.content) > 1000

    route = live_server.get("/admin/products")
    assert route.status_code == 200
    assert "text/html" in route.headers.get("content-type", "")
    assert "<div id=" in route.text

    not_found = live_server.get("/api/v1/does-not-exist")
    assert not_found.status_code == 404


def test_live_customer_journey_matching_frontend(live_server: httpx.Client):
    """按前端的真实调用顺序验证 C 端链路：游客会话 -> 公开商品检索 -> 加购 -> 我的地址 -> 下单 -> 支付。"""
    client = live_server
    guest = client.post("/api/v1/auth/guest-session", json={"display_name": "前端联调访客"})
    assert guest.status_code == 200
    guest_token = guest.json()["access_token"]

    search = client.get("/api/v1/products/search", headers=_auth(guest_token), params={"page_size": 10})
    assert search.status_code == 200, search.text
    payload = search.json()
    assert payload["total"] >= 5
    sku = None
    for product in payload["items"]:
        for candidate in product.get("skus", []):
            if candidate["sellable_qty"] > 0:
                sku = candidate
                break
        if sku:
            break
    assert sku, "公开列表必须返回可售 SKU（前端加购依赖）"

    customer = client.post("/api/v1/auth/customer/login",
                           json={"username": "buyer_li", "password": DEV_PASSWORD}).json()
    ctoken = customer["access_token"]
    me = client.get("/api/v1/auth/me", headers=_auth(ctoken)).json()
    assert me["customer_id"], "/auth/me 必须返回 customer_id"

    added = client.post("/api/v1/cart/items", headers=_auth(ctoken, True),
                        json={"sku_id": sku["id"], "quantity": 1, "channel_account_id": 1})
    assert added.status_code == 200, added.text
    assert added.json()["items"][0]["available"] is True

    addresses = client.get("/api/v1/customers/me/addresses", headers=_auth(ctoken))
    assert addresses.status_code == 200 and addresses.json(), "客户必须有可用收货地址"

    created = client.post("/api/v1/orders", headers=_auth(ctoken, True), json={
        "items": [{"sku_id": sku["id"], "quantity": 1}],
        "channel_account_id": 1,
        "address_id": addresses.json()[0]["id"],
    })
    assert created.status_code == 200, created.text
    order = created.json()
    assert order["payable_amount"] == sku["price"]

    paid = client.post(f"/api/v1/payments/{order['payments'][0]['id']}/mock-succeed", headers=_auth(ctoken, True))
    assert paid.status_code == 200 and paid.json()["order"]["status"] == "PAID"

    mine = client.get("/api/v1/orders", headers=_auth(ctoken), params={"page_size": 5}).json()
    assert any(item["order_no"] == order["order_no"] for item in mine["items"])
