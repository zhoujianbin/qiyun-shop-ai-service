from tests.conftest import auth, customer_token, login, new_key, staff_token


def test_staff_login_success_and_me(client):
    token = staff_token(client)
    me = client.get("/api/v1/auth/me", headers=auth(token))
    assert me.status_code == 200
    body = me.json()
    assert body["party"] == "STAFF"
    assert body["is_super_admin"] is True
    assert "shop:order:read" in body["permissions"]


def test_login_wrong_password_returns_401(client):
    resp = client.post("/api/v1/auth/staff/login", json={"username": "admin", "password": "bad-password"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_INVALID_CREDENTIALS"


def test_customer_cannot_use_staff_portal(client):
    resp = client.post("/api/v1/auth/staff/login", json={"username": "buyer_zhang", "password": "Qiyun@2026#Dev"})
    assert resp.status_code == 403
    assert resp.json()["code"] == "AUTH_WRONG_PORTAL"


def test_register_and_login_new_customer(client):
    payload = {"username": "buyer_new_01", "password": "NewBuyer@2026", "display_name": "新客户", "phone": "13911112222"}
    created = client.post("/api/v1/auth/customer/register", json=payload)
    assert created.status_code == 200, created.text
    token = created.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers=auth(token))
    assert me.json()["customer_id"] is not None
    assert client.post("/api/v1/auth/customer/login", json={"username": payload["username"], "password": payload["password"]}).status_code == 200


def test_refresh_rotates_and_old_token_is_rejected(client):
    resp = client.post("/api/v1/auth/customer/login", json={"username": "buyer_li", "password": "Qiyun@2026#Dev"})
    refresh_token = resp.json()["refresh_token"]
    first = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert first.status_code == 200
    assert first.json()["refresh_token"] != refresh_token
    second = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert second.status_code == 401
    assert second.json()["code"] == "AUTH_REFRESH_INVALID"


def test_logout_revokes_refresh_token(client):
    resp = client.post("/api/v1/auth/customer/login", json={"username": "buyer_wang", "password": "Qiyun@2026#Dev"})
    body = resp.json()
    out = client.post("/api/v1/auth/logout", headers=auth(body["access_token"]))
    assert out.status_code == 200 and out.json()["revoked"] >= 1
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert replay.status_code == 401


def test_change_password_revokes_sessions(client):
    token = customer_token(client, "buyer_chen")
    resp = client.post("/api/v1/auth/password/change", headers=auth(token, new_key()),
                       json={"old_password": "Qiyun@2026#Dev", "new_password": "Changed@2026#Dev"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["revoked_sessions"] >= 1
    assert login(client, "buyer_chen", password="Changed@2026#Dev", staff=False)
    revert = client.post("/api/v1/auth/password/change", headers=auth(login(client, "buyer_chen", password="Changed@2026#Dev", staff=False), new_key()),
                         json={"old_password": "Changed@2026#Dev", "new_password": "Qiyun@2026#Dev"})
    assert revert.status_code == 200


def test_guest_session_can_read_public_catalog(client):
    guest = client.post("/api/v1/auth/guest-session", json={"display_name": "访客A"})
    assert guest.status_code == 200
    token = guest.json()["access_token"]
    products = client.get("/api/v1/products/search", headers=auth(token))
    assert products.status_code == 200
    assert products.json()["total"] >= 5
