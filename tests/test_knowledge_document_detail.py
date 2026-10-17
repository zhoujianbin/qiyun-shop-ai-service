"""二期文档详情：曾因缺 func 导入直接 500（无测试覆盖），这里补回归。"""
import uuid

from app.core.db import SessionLocal
from app.models.generated import Chunk, Document, DocumentVersion
from tests.conftest import auth, staff_token


def _seed_document() -> int:
    with SessionLocal() as db:
        doc = Document(tenant_id=1, document_id=f"KB-DETAIL-TEST-{uuid.uuid4().hex[:8]}",
                       title="详情回归用例",
                       category="support_sop", status="ACTIVE", current_version=1)
        db.add(doc)
        db.flush()
        version = DocumentVersion(tenant_id=1, document_pk=doc.id, version=1,
                                  content_md="# 标题\n正文", checksum="x" * 64, status="ACTIVE",
                                  source_kind="MANUAL")
        db.add(version)
        db.flush()
        db.add(Chunk(tenant_id=1, document_version_id=version.id, ord=1,
                     title_path="标题", content="正文", identity_level="public"))
        db.commit()
        return doc.id


def test_document_detail_returns_chunk_count_and_versions(client):
    document_pk = _seed_document()
    token = staff_token(client, "admin")
    response = client.get(f"/api/v1/knowledge/documents/{document_pk}", headers=auth(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["chunk_count"] == 1
    assert isinstance(body["versions"], list) and body["versions"]
    assert body["active_version"]["version"] == 1


def test_document_detail_not_found(client):
    token = staff_token(client, "admin")
    response = client.get("/api/v1/knowledge/documents/99999999", headers=auth(token))
    assert response.status_code == 404


def test_document_list_does_not_compute_chunk_count(client):
    """列表不逐条算切片数（避免 N+1）；详情才给 chunk_count。"""
    _seed_document()
    token = staff_token(client, "admin")
    page = client.get("/api/v1/knowledge/documents", headers=auth(token),
                      params={"page_size": 5}).json()
    assert page["items"] and all(item.get("chunk_count") is None for item in page["items"])
