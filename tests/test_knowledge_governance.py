"""治理报告与概览：五类报告有真实数据、可下钻、概览与列表一致。"""
import uuid

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.generated import Document
from tests.conftest import auth, new_key, staff_token

REPORT_KEYS = {"duplicate", "expired", "orphan", "conflict", "inconsistent", "counts"}


def _import_doc(client, token, document_id, title, category="product"):
    payload = (
        "---\n"
        f"document_id: {document_id}\n"
        f"title: {title}\n"
        f"category: {category}\n"
        'version: "1.0"\n'
        'effective_date: "2026-01-01"\n'
        "owner: 测试\n"
        "status: ACTIVE\n"
        "---\n"
        f"# {title}\n\n治理探针正文。\n"
    ).encode("utf-8")
    files = [("files", (f"{document_id}.md", payload, "text/markdown"))]
    assert client.post("/api/v1/knowledge/import/jobs", headers=auth(token, new_key()),
                       files=files).status_code == 200


def test_report_has_five_categories(client):
    token = staff_token(client)
    response = client.get("/api/v1/knowledge/governance/report", headers=auth(token, new_key()))
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == REPORT_KEYS
    assert set(body["counts"]) == {"duplicate", "expired", "orphan", "conflict", "inconsistent"}


def test_duplicate_and_inconsistent_are_detected(client):
    token = staff_token(client)
    suffix = uuid.uuid4().hex[:6]
    title = f"同名治理探针 {suffix}"
    _import_doc(client, token, f"KB-GOV-DUP-A-{suffix}", title)
    _import_doc(client, token, f"KB-GOV-DUP-B-{suffix}", title)
    _import_doc(client, token, f"KB-GOV-INC-{suffix}", f"商品范围探针 {suffix}")

    with SessionLocal() as db:
        document = db.execute(
            select(Document).where(Document.document_id == f"KB-GOV-INC-{suffix}")
        ).scalar_one()
        document.product_scope = f"NOPE-{suffix}"
        db.commit()

    body = client.get("/api/v1/knowledge/governance/report",
                      headers=auth(token, new_key())).json()
    assert any(item["type"] == "DUPLICATE" and title in item["detail"] or
               item["type"] == "DUPLICATE" and item["title"] == title
               for item in body["duplicate"])
    assert any(item["document_id"] == f"KB-GOV-INC-{suffix}" for item in body["inconsistent"])
    assert body["counts"]["duplicate"] == len(body["duplicate"])


def test_report_items_carry_drilldown_filters(client):
    token = staff_token(client)
    body = client.get("/api/v1/knowledge/governance/report",
                      headers=auth(token, new_key())).json()
    for category in ("duplicate", "expired", "orphan", "conflict", "inconsistent"):
        for item in body[category][:3]:
            assert isinstance(item["filter"], dict) and item["filter"]


def test_overview_matches_list_totals(client):
    token = staff_token(client)
    overview = client.get("/api/v1/knowledge/overview", headers=auth(token, new_key())).json()
    page = client.get("/api/v1/knowledge/documents?page_size=1",
                      headers=auth(token, new_key())).json()
    assert overview["documents"] == page["total"]
    assert overview["chunks"] >= overview["documents"]
    assert set(overview["governance"]) == {"duplicate", "expired", "orphan", "conflict", "inconsistent"}
