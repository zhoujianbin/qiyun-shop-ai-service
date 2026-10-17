"""审核：认领互斥、决定留痕、自审策略、锚定批注。"""
import uuid

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.errors import Conflict
from app.models.generated import Document, DocumentVersion
from app.services import knowledge_review
from tests.conftest import auth, new_key, staff_token


def _md(document_id: str) -> bytes:
    return (
        "---\n"
        f"document_id: {document_id}\n"
        f"title: 审核测试 {document_id}\n"
        "category: product\n"
        'version: "1.0"\n'
        'effective_date: "2026-01-01"\n'
        "owner: 测试\n"
        "status: ACTIVE\n"
        "---\n"
        "# 正文\n\n用于审核流程的内容。\n"
    ).encode("utf-8")


def _pending_task(client, token) -> tuple[int, int]:
    suffix = uuid.uuid4().hex[:8]
    document_id = f"KB-REV-{suffix}"
    files = [("files", (f"{document_id}.md", _md(document_id), "text/markdown"))]
    assert client.post("/api/v1/knowledge/import/jobs", headers=auth(token, new_key()),
                       files=files).status_code == 200
    with SessionLocal() as db:
        document = db.execute(select(Document).where(Document.document_id == document_id)).scalar_one()
        version = db.execute(
            select(DocumentVersion).where(DocumentVersion.document_pk == document.id)
        ).scalar_one()
        version_id = version.id
    assert client.post(f"/api/v1/knowledge/versions/{version_id}/submit",
                       headers=auth(token, new_key())).status_code == 200
    tasks = client.get("/api/v1/knowledge/review/tasks?status=PENDING",
                       headers=auth(token, new_key())).json()
    task = next(row for row in tasks if row["document_version_id"] == version_id)
    return task["id"], version_id


def test_claim_is_exclusive(client):
    token = staff_token(client)
    task_id, _ = _pending_task(client, token)
    claimed = client.post(f"/api/v1/knowledge/review/tasks/{task_id}/claim",
                          headers=auth(token, new_key()))
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["status"] == "CLAIMED"

    with SessionLocal() as db:
        with pytest.raises(Conflict):
            knowledge_review.claim(db, {"id": 999, "party": "STAFF"}, task_id)


def test_decision_requires_reason(client):
    token = staff_token(client)
    task_id, _ = _pending_task(client, token)
    response = client.post(f"/api/v1/knowledge/review/tasks/{task_id}/decide",
                           headers=auth(token, new_key()),
                           json={"decision": "APPROVED", "note": ""})
    assert response.status_code == 422, response.text


def test_changes_requested_returns_version_to_draft(client):
    token = staff_token(client)
    task_id, version_id = _pending_task(client, token)
    response = client.post(f"/api/v1/knowledge/review/tasks/{task_id}/decide",
                           headers=auth(token, new_key()),
                           json={"decision": "CHANGES_REQUESTED", "note": "请补充参数表"})
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        assert db.get(DocumentVersion, version_id).status == "DRAFT"


def test_self_review_is_marked(client):
    token = staff_token(client)
    task_id, version_id = _pending_task(client, token)
    response = client.post(f"/api/v1/knowledge/review/tasks/{task_id}/decide",
                           headers=auth(token, new_key()),
                           json={"decision": "APPROVED", "note": "自审通过"})
    assert response.status_code == 200, response.text
    assert response.json()["self_review"] is True

    with SessionLocal() as db:
        version = db.get(DocumentVersion, version_id)
        assert version.created_by is not None


def test_self_review_can_be_forbidden(client, monkeypatch):
    token = staff_token(client)
    task_id, _ = _pending_task(client, token)
    monkeypatch.setattr(settings, "knowledge_allow_self_review", False)
    response = client.post(f"/api/v1/knowledge/review/tasks/{task_id}/decide",
                           headers=auth(token, new_key()),
                           json={"decision": "APPROVED", "note": "自审"})
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "SELF_REVIEW_FORBIDDEN"


def test_comment_requires_anchor(client):
    token = staff_token(client)
    task_id, _ = _pending_task(client, token)
    rejected = client.post(f"/api/v1/knowledge/review/tasks/{task_id}/comments",
                           headers=auth(token, new_key()),
                           json={"anchor": {}, "content": "这里要改"})
    assert rejected.status_code == 422, rejected.text

    accepted = client.post(f"/api/v1/knowledge/review/tasks/{task_id}/comments",
                           headers=auth(token, new_key()),
                           json={"anchor": {"title_path": "正文", "chunk_ord": 0}, "content": "这里要改"})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["anchor"]["chunk_ord"] == 0

    listed = client.get(f"/api/v1/knowledge/review/tasks/{task_id}/comments",
                        headers=auth(token, new_key())).json()
    assert len(listed) == 1
