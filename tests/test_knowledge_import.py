"""导入任务：去重、幂等、失败隔离、切片预览、异步向量化与重试。"""
import uuid

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.generated import Chunk, Document, DocumentVersion
from app.services import knowledge_embedding, knowledge_import
from tests.conftest import auth, new_key, staff_token


def _doc(document_id: str, title: str, body: str) -> bytes:
    front = (
        "---\n"
        f"document_id: {document_id}\n"
        f"title: {title}\n"
        "category: product\n"
        'version: "1.0"\n'
        'effective_date: "2026-01-01"\n'
        "owner: 测试\n"
        "status: ACTIVE\n"
        "---\n"
    )
    return (front + body).encode("utf-8")


def _files(*items: tuple[str, bytes]) -> list[tuple[str, tuple[str, bytes, str]]]:
    """httpx 多文件：字段名固定 files，同名重复出现即多文件。"""
    return [("files", (name, payload, "text/markdown")) for name, payload in items]


def test_import_creates_documents_versions_and_pending_chunks(client):
    token = staff_token(client)
    suffix = uuid.uuid4().hex[:8]
    payloads = _files(
        (f"a-{suffix}.md", _doc(f"KB-IMP-A-{suffix}", "甲文档", "# 甲\n\n甲的第一段内容。\n")),
        (f"b-{suffix}.md", _doc(f"KB-IMP-B-{suffix}", "乙文档", "# 乙\n\n乙的第一段内容。\n")),
    )
    response = client.post(
        "/api/v1/knowledge/import/jobs", headers=auth(token, new_key()), files=payloads
    )
    assert response.status_code == 200, response.text
    job = response.json()
    assert job["total"] == 2 and job["succeeded"] == 2 and job["failed"] == 0
    assert job["status"] == "DONE"
    assert job["errors"] == []

    with SessionLocal() as db:
        document = db.execute(
            select(Document).where(Document.document_id == f"KB-IMP-A-{suffix}")
        ).scalar_one()
        version = db.execute(
            select(DocumentVersion).where(DocumentVersion.document_pk == document.id)
        ).scalar_one()
        chunks = db.execute(
            select(Chunk).where(Chunk.document_version_id == version.id)
        ).scalars().all()
    assert version.version == 1 and version.status == "DRAFT"
    assert version.source_kind == "MD_BUNDLE"
    assert chunks and all(chunk.embedding_status == "PENDING" for chunk in chunks)
    assert chunks[0].metadata_json["source_line_start"] >= 1


def test_reimport_is_skipped_and_does_not_duplicate(client):
    token = staff_token(client)
    suffix = uuid.uuid4().hex[:8]
    payloads = _files(
        (f"dup-{suffix}.md", _doc(f"KB-DUP-{suffix}", "重复文档", "# 重复\n\n同一份内容。\n"))
    )
    first = client.post("/api/v1/knowledge/import/jobs", headers=auth(token, new_key()), files=payloads)
    assert first.json()["succeeded"] == 1

    second = client.post("/api/v1/knowledge/import/jobs", headers=auth(token, new_key()), files=payloads)
    body = second.json()
    assert body["succeeded"] == 0 and body["skipped"] == 1

    with SessionLocal() as db:
        count = len(db.execute(
            select(Document).where(Document.document_id == f"KB-DUP-{suffix}")
        ).scalars().all())
    assert count == 1


def test_bad_file_does_not_block_the_batch(client):
    token = staff_token(client)
    suffix = uuid.uuid4().hex[:8]
    payloads = _files(
        (f"good-{suffix}.md", _doc(f"KB-MIX-{suffix}", "好文件", "# 好\n\n正常内容。\n")),
        (f"bad-{suffix}.md", "# 没有 front matter\n".encode("utf-8")),
    )
    response = client.post(
        "/api/v1/knowledge/import/jobs", headers=auth(token, new_key()), files=payloads
    )
    body = response.json()
    assert body["status"] == "PARTIAL"
    assert body["succeeded"] == 1 and body["failed"] == 1
    assert body["errors"][0]["file"].startswith("bad-")
    assert "front matter" in body["errors"][0]["reason"]


def test_idempotency_key_returns_same_job(client):
    token = staff_token(client)
    suffix = uuid.uuid4().hex[:8]
    payloads = _files(
        (f"idem-{suffix}.md", _doc(f"KB-IDEM-{suffix}", "幂等文档", "# 幂等\n\n内容。\n"))
    )
    key = new_key()
    first = client.post("/api/v1/knowledge/import/jobs", headers=auth(token, key), files=payloads)
    second = client.post("/api/v1/knowledge/import/jobs", headers=auth(token, key), files=payloads)
    assert first.json()["id"] == second.json()["id"]


def test_oversize_file_is_rejected(client, monkeypatch):
    token = staff_token(client)
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    payloads = _files(("big.md", _doc("KB-BIG-001", "大文件", "# 大\n\n内容。\n")))
    response = client.post(
        "/api/v1/knowledge/import/jobs", headers=auth(token, new_key()), files=payloads
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VALIDATION_FAILED"
    assert response.json()["request_id"]


def test_preview_chunks_returns_ord_and_line_numbers(client):
    token = staff_token(client)
    response = client.post(
        "/api/v1/knowledge/preview-chunks",
        headers=auth(token),
        json={"content_md": "# 一级\n\n第一段内容。\n\n## 二级\n\n第二段内容。\n"},
    )
    assert response.status_code == 200, response.text
    items = response.json()
    assert items and items[0]["ord"] == 0
    assert items[-1]["title_path"] == "一级 / 二级"
    assert all(item["char_count"] == len(item["content"]) for item in items)


def test_worker_fills_vectors_and_requeues_failures(client):
    token = staff_token(client)
    suffix = uuid.uuid4().hex[:8]
    payloads = _files(
        (f"vec-{suffix}.md", _doc(f"KB-VEC-{suffix}", "向量文档", "# 向量\n\n需要向量化的内容。\n"))
    )
    client.post("/api/v1/knowledge/import/jobs", headers=auth(token, new_key()), files=payloads)

    with SessionLocal() as db:
        result = knowledge_embedding.run_once(db, batch_size=32)
        assert result["ready"] > 0
        pending = db.execute(
            select(Chunk).where(Chunk.embedding_status == "PENDING")
        ).scalars().all()
        assert pending == []

        victim = db.execute(select(Chunk).limit(1)).scalars().one()
        victim.embedding_status = "FAILED"
        db.commit()
        requeued = knowledge_import.requeue_failed_chunks(db)
        db.commit()
        assert requeued >= 1
        assert db.get(Chunk, victim.id).embedding_status == "PENDING"
