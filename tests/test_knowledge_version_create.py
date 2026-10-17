"""后台手动新建版本：版本号递增、切片重建、404、权限。"""
import uuid

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.generated import Chunk, Document, DocumentVersion
from tests.conftest import auth, customer_token, new_key, staff_token


def _import(client, token, document_id: str):
    payload = (
        "---\n"
        f"document_id: {document_id}\n"
        f"title: 编辑器保存 {document_id}\n"
        "category: product\n"
        'version: "1.0"\n'
        'effective_date: "2026-01-01"\n'
        "owner: 测试\n"
        "status: ACTIVE\n"
        "---\n"
        "# 第一节\n\n原始内容。\n"
    ).encode("utf-8")
    files = [("files", (f"{document_id}.md", payload, "text/markdown"))]
    assert client.post("/api/v1/knowledge/import/jobs", headers=auth(token, new_key()),
                       files=files).status_code == 200
    with SessionLocal() as db:
        document = db.execute(select(Document).where(Document.document_id == document_id)).scalar_one()
        return document.id


def test_create_version_increments_and_rechunks(client):
    token = staff_token(client)
    suffix = uuid.uuid4().hex[:8]
    document_pk = _import(client, token, f"KB-EDT-{suffix}")

    response = client.post(
        f"/api/v1/knowledge/documents/{document_pk}/versions",
        headers=auth(token, new_key()),
        json={"content_md": "# 第一节\n\n修改后的内容，多了一段说明。\n", "change_summary": "补充说明"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == 2
    assert body["status"] == "DRAFT"
    assert body["source_kind"] == "MANUAL"
    assert body["change_summary"] == "补充说明"

    with SessionLocal() as db:
        versions = db.execute(
            select(DocumentVersion).where(DocumentVersion.document_pk == document_pk)
            .order_by(DocumentVersion.version)
        ).scalars().all()
        assert [row.version for row in versions] == [1, 2]
        assert versions[0].status == "DRAFT"  # v1 未被改动
        chunks = db.execute(
            select(Chunk).where(Chunk.document_version_id == versions[1].id)
        ).scalars().all()
    assert chunks, "新版本必须重新切片"
    assert all(chunk.embedding_status == "PENDING" for chunk in chunks)
    assert "修改后的内容" in "".join(chunk.content for chunk in chunks)


def test_create_version_unknown_document_returns_404(client):
    token = staff_token(client)
    response = client.post(
        "/api/v1/knowledge/documents/99999999/versions",
        headers=auth(token, new_key()),
        json={"content_md": "# x\n\n内容。\n"},
    )
    assert response.status_code == 404, response.text


def test_create_version_requires_write_permission(client):
    suffix = uuid.uuid4().hex[:8]
    admin = staff_token(client)
    document_pk = _import(client, admin, f"KB-EDT-PERM-{suffix}")
    buyer = customer_token(client, "buyer_zhang")
    response = client.post(
        f"/api/v1/knowledge/documents/{document_pk}/versions",
        headers=auth(buyer, new_key()),
        json={"content_md": "# x\n\n内容。\n"},
    )
    assert response.status_code == 403, response.text


def test_create_version_rejects_empty_content(client):
    token = staff_token(client)
    suffix = uuid.uuid4().hex[:8]
    document_pk = _import(client, token, f"KB-EDT-EMPTY-{suffix}")
    response = client.post(
        f"/api/v1/knowledge/documents/{document_pk}/versions",
        headers=auth(token, new_key()),
        json={"content_md": ""},
    )
    assert response.status_code == 422, response.text
