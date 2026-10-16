from tests.conftest import auth, customer_token, new_key

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 128


def test_attachment_upload_download_and_validation(client):
    ctoken = customer_token(client, "buyer_zhang")
    uploaded = client.post("/api/v1/attachments", headers=auth(ctoken),
                           files={"file": ("evidence.png", PNG, "image/png")},
                           data={"owner_type": "after_sales"})
    assert uploaded.status_code == 200, uploaded.text
    body = uploaded.json()
    assert body["size_bytes"] == len(PNG)
    assert body["content_type"] == "image/png"
    assert body["download_url"] == f"/api/v1/attachments/{body['id']}"
    assert len(body["checksum_sha256"]) == 64

    download = client.get(f"/api/v1/attachments/{body['id']}", headers=auth(ctoken))
    assert download.status_code == 200
    assert download.content == PNG
    assert download.headers["content-type"].startswith("image/png")

    unauthorized = client.get(f"/api/v1/attachments/{body['id']}")
    assert unauthorized.status_code == 401

    bad_ext = client.post("/api/v1/attachments", headers=auth(ctoken),
                          files={"file": ("payload.exe", b"MZ\x90\x00", "application/octet-stream")})
    assert bad_ext.status_code == 422

    bad_magic = client.post("/api/v1/attachments", headers=auth(ctoken),
                            files={"file": ("fake.png", b"%PDF-1.4 not really png", "image/png")})
    assert bad_magic.status_code == 422

    mime_mismatch = client.post("/api/v1/attachments", headers=auth(ctoken),
                                files={"file": ("note.txt", b"hello", "image/png")})
    assert mime_mismatch.status_code == 422

    listed = client.get("/api/v1/attachments", headers=auth(ctoken), params={"owner_type": "after_sales"})
    assert listed.status_code == 403  # 客户无售后查看权限，仅员工可列附件


def test_attachment_can_be_bound_to_after_sales(client):
    ctoken = customer_token(client, "buyer_li")
    uploaded = client.post("/api/v1/attachments", headers=auth(ctoken),
                           files={"file": ("evidence.txt", "到货破损，附件说明".encode("utf-8"), "text/plain")},
                           data={"owner_type": "after_sales"}).json()
    from tests.helpers import create_order, first_purchasable_sku

    sku = first_purchasable_sku(client)["sku"]
    order = create_order(client, ctoken, sku_id=sku["id"], quantity=1)
    application = client.post("/api/v1/after-sales/applications", headers=auth(ctoken, new_key()), json={
        "order_id": order["id"], "type": "REFUND_ONLY", "reason_code": "DAMAGE_ON_ARRIVAL",
        "description": "到货破损", "evidence": [uploaded["id"]],
        "expect_amount": float(order["payable_amount"]),
        "items": [{"order_item_id": order["items"][0]["id"], "quantity": 1}]})
    assert application.status_code == 200, application.text
    assert application.json()["evidence"] == [uploaded["id"]]
