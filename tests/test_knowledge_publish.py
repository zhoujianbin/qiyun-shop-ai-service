"""版本与发布：提交审核、门禁、单一 ACTIVE、定时生效、回滚、审计与事件。"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text

from app.core.db import SessionLocal
from app.models.generated import AuditLog, Chunk, Document, DocumentVersion, OutboxEvent, Rule
from app.services import knowledge_governance, knowledge_rule
from tests.conftest import auth, new_key, staff_token


def _md(document_id: str, body: str) -> bytes:
    front = (
        "---\n"
        f"document_id: {document_id}\n"
        f"title: 发布测试 {document_id}\n"
        "category: product\n"
        'version: "1.0"\n'
        'effective_date: "2026-01-01"\n'
        "owner: 测试\n"
        "status: ACTIVE\n"
        "---\n"
    )
    return (front + body).encode("utf-8")


def _import(client, token, document_id: str, body: str, name: str | None = None):
    files = [("files", (name or f"{document_id}.md", _md(document_id, body), "text/markdown"))]
    response = client.post("/api/v1/knowledge/import/jobs",
                           headers=auth(token, new_key()), files=files)
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        document = db.execute(
            select(Document).where(Document.document_id == document_id)
        ).scalar_one()
        version = db.execute(
            select(DocumentVersion).where(DocumentVersion.document_pk == document.id)
            .order_by(DocumentVersion.version.desc())
        ).scalars().first()
        return document.id, version.id


def test_submit_creates_review_task(client):
    token = staff_token(client)
    suffix = uuid.uuid4().hex[:8]
    _, version_id = _import(client, token, f"KB-PUB-SUB-{suffix}", "# 甲\n\n甲的正文内容。\n")
    response = client.post(f"/api/v1/knowledge/versions/{version_id}/submit",
                           headers=auth(token, new_key()))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "REVIEWING"

    tasks = client.get("/api/v1/knowledge/review/tasks", headers=auth(token, new_key())).json()
    assert any(task["document_version_id"] == version_id for task in tasks)


def test_publish_requires_change_summary(client):
    token = staff_token(client)
    suffix = uuid.uuid4().hex[:8]
    _, version_id = _import(client, token, f"KB-PUB-SUM-{suffix}", "# 乙\n\n乙的正文内容。\n")
    response = client.post(f"/api/v1/knowledge/versions/{version_id}/publish",
                           headers=auth(token, new_key()), json={"change_summary": ""})
    assert response.status_code == 422, response.text


def test_publish_sets_active_and_returns_info(client):
    token = staff_token(client)
    suffix = uuid.uuid4().hex[:8]
    document_pk, version_id = _import(client, token, f"KB-PUB-OK-{suffix}", "# 丙\n\n丙的正文内容。\n")
    response = client.post(f"/api/v1/knowledge/versions/{version_id}/publish",
                           headers=auth(token, new_key()),
                           json={"change_summary": "首次发布"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ACTIVE"
    info = body["publish_info"]
    assert info["change_summary"] == "首次发布"
    assert info["citation_count"] == 0
    assert set(info["affected_scope"]) == {"product_scope", "channel_scope"}

    with SessionLocal() as db:
        document = db.get(Document, document_pk)
        assert document.status == "ACTIVE" and document.current_version == 1
        audits = db.execute(select(AuditLog).where(AuditLog.action == "knowledge.version.publish")).scalars().all()
        events = db.execute(select(OutboxEvent).where(
            OutboxEvent.event_type == "knowledge.version.published")).scalars().all()
    assert audits and events


def test_second_publish_archives_previous(client):
    token = staff_token(client)
    suffix = uuid.uuid4().hex[:8]
    document_id = f"KB-PUB-V2-{suffix}"
    document_pk, first = _import(client, token, document_id, "# 丁\n\n第一版正文。\n")
    client.post(f"/api/v1/knowledge/versions/{first}/publish", headers=auth(token, new_key()),
                json={"change_summary": "v1"})

    _, second = _import(client, token, document_id, "# 丁\n\n第二版正文，内容不同。\n",
                        name=f"{document_id}-v2.md")
    published = client.post(f"/api/v1/knowledge/versions/{second}/publish",
                            headers=auth(token, new_key()), json={"change_summary": "v2"})
    assert published.status_code == 200, published.text
    assert published.json()["version"] == 2

    with SessionLocal() as db:
        active = db.execute(
            select(DocumentVersion).where(
                DocumentVersion.document_pk == document_pk,
                DocumentVersion.status == "ACTIVE",
            )
        ).scalars().all()
        old = db.execute(
            select(DocumentVersion).where(
                DocumentVersion.document_pk == document_pk,
                DocumentVersion.version == 1,
            )
        ).scalar_one()
    assert len(active) == 1 and active[0].version == 2
    assert old.status == "ARCHIVED"


def test_publish_blocked_when_no_chunks(client):
    token = staff_token(client)
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        document = Document(tenant_id=1, document_id=f"KB-PUB-EMPTY-{suffix}", title="空版本",
                            category="product", owner="测试", status="DRAFT")
        db.add(document)
        db.flush()
        version = DocumentVersion(tenant_id=1, document_pk=document.id, version=1,
                                  content_md="# 空", checksum="x" * 64, status="DRAFT")
        db.add(version)
        db.commit()
        version_id = version.id
    response = client.post(f"/api/v1/knowledge/versions/{version_id}/publish",
                           headers=auth(token, new_key()), json={"change_summary": "试试"})
    assert response.status_code == 422, response.text
    assert any("切片为空" in reason for reason in response.json()["details"]["reasons"])


def test_publish_blocked_by_open_block_conflict(client):
    token = staff_token(client)
    suffix = uuid.uuid4().hex[:8]
    group = f"pub_block_{suffix}"
    for name, decision in (("A", "ALLOW_RETURN"), ("B", "DENY_RETURN")):
        client.post("/api/v1/knowledge/rules", headers=auth(token, new_key()), json={
            "rule_id": f"PUB-BLOCK-{name}-{suffix}",
            "condition": {"issue_type": "conflict_probe"},
            "action": {"decision": decision},
            "status": "ACTIVE",
            "conflict_group": group,
        })
    _, version_id = _import(client, token, f"KB-PUB-BLOCK-{suffix}", "# 戊\n\n戊的正文。\n")
    blocked = client.post(f"/api/v1/knowledge/versions/{version_id}/publish",
                          headers=auth(token, new_key()), json={"change_summary": "被拦"})
    assert blocked.status_code == 422, blocked.text
    assert any("阻断级规则冲突" in reason for reason in blocked.json()["details"]["reasons"])

    # 解决冲突后放行
    with SessionLocal() as db:
        for row in knowledge_rule.open_blocking_conflicts(db):
            row.status = "RESOLVED"
            row.resolved_by = 1
        db.commit()
    passed = client.post(f"/api/v1/knowledge/versions/{version_id}/publish",
                         headers=auth(token, new_key()), json={"change_summary": "放行"})
    assert passed.status_code == 200, passed.text


def test_scheduled_publish_activates_via_worker(client):
    token = staff_token(client)
    suffix = uuid.uuid4().hex[:8]
    document_pk, version_id = _import(client, token, f"KB-PUB-SCH-{suffix}", "# 己\n\n己的正文。\n")
    future = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
    response = client.post(f"/api/v1/knowledge/versions/{version_id}/publish",
                           headers=auth(token, new_key()),
                           json={"change_summary": "定时", "effective_from": future})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "SCHEDULED"

    with SessionLocal() as db:
        version = db.get(DocumentVersion, version_id)
        version.effective_from = datetime.now(timezone.utc) - timedelta(seconds=5)
        db.commit()
        result = knowledge_governance.activate_due(db)
        db.commit()
        assert result["activated"] >= 1
        assert db.get(DocumentVersion, version_id).status == "ACTIVE"
        assert db.get(Document, document_pk).current_version == 1


def test_rollback_creates_new_active_version(client):
    token = staff_token(client)
    suffix = uuid.uuid4().hex[:8]
    document_id = f"KB-PUB-RB-{suffix}"
    document_pk, version_one = _import(client, token, document_id, "# 庚\n\n回滚目标正文。\n")
    client.post(f"/api/v1/knowledge/versions/{version_one}/publish", headers=auth(token, new_key()),
                json={"change_summary": "v1"})
    _, version_two = _import(client, token, document_id, "# 庚\n\n第二版不同正文。\n",
                             name=f"{document_id}-v2.md")
    client.post(f"/api/v1/knowledge/versions/{version_two}/publish", headers=auth(token, new_key()),
                json={"change_summary": "v2"})

    rolled = client.post(f"/api/v1/knowledge/versions/{version_one}/rollback",
                         headers=auth(token, new_key()))
    assert rolled.status_code == 200, rolled.text
    assert rolled.json()["version"] == 3

    with SessionLocal() as db:
        one = db.get(DocumentVersion, version_one)
        three = db.get(DocumentVersion, rolled.json()["id"])
        active = db.execute(
            select(DocumentVersion).where(DocumentVersion.document_pk == document_pk,
                                          DocumentVersion.status == "ACTIVE")
        ).scalars().all()
        chunks = db.execute(
            select(Chunk).where(Chunk.document_version_id == three.id)
        ).scalars().all()
        assert db.get(Document, document_pk).current_version == 3
        origin_chunks = db.execute(
            select(Chunk).where(Chunk.document_version_id == one.id)
        ).scalars().all()
    assert three.content_md == one.content_md
    assert len(active) == 1 and active[0].id == three.id
    # 回滚复制切片：内容与顺序一致；有向量则直接 READY，否则继续等待 worker
    assert len(chunks) == len(origin_chunks)
    assert [chunk.ord for chunk in chunks] == [chunk.ord for chunk in origin_chunks]
