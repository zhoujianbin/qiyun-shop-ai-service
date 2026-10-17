"""四期本体接口：列表、创建草稿、审核、图谱。"""
from tests.conftest import auth, new_key, staff_token


def _admin(client):
    return staff_token(client, "admin")


def test_list_entities_requires_read_permission_and_returns_items(client):
    token = _admin(client)
    response = client.get("/api/v1/knowledge/ontology/entities",
                          headers=auth(token), params={"page_size": 5})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["items"] and "meta" in body
    assert {"id", "code", "kind", "name", "status"} <= set(body["items"][0])


def test_create_draft_then_review_approves(client):
    token = _admin(client)
    created = client.post("/api/v1/knowledge/ontology/entities",
                          headers=auth(token, new_key()),
                          json={"code": "EV-TEST-ENTITY", "kind": "part", "name": "评测临时部件"})
    assert created.status_code == 200, created.text
    entity = created.json()
    assert entity["status"] == "DRAFT"

    reviewed = client.post("/api/v1/knowledge/ontology/review",
                           headers=auth(token, new_key()),
                           json={"entity_ids": [entity["id"]], "action": "approve"})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["updated"] == 1

    listed = client.get("/api/v1/knowledge/ontology/entities",
                        headers=auth(token), params={"keyword": "EV-TEST-ENTITY"}).json()
    assert listed["items"][0]["status"] == "APPROVED"


def test_graph_is_depth_limited(client):
    token = _admin(client)
    entities = client.get("/api/v1/knowledge/ontology/entities",
                          headers=auth(token), params={"kind": "product", "page_size": 1}).json()
    root = entities["items"][0]
    response = client.get("/api/v1/knowledge/ontology/graph", headers=auth(token),
                          params={"entity_id": root["id"], "depth": 2})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["depth"] == 2
    assert all(node["depth"] <= 2 for node in body["nodes"])


def test_write_requires_write_permission(client):
    from tests.conftest import customer_token

    client_token = customer_token(client)
    response = client.post("/api/v1/knowledge/ontology/entities",
                           headers=auth(client_token, new_key()),
                           json={"code": "EV-DENIED", "kind": "part"})
    assert response.status_code == 403
