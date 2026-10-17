"""混合检索：引用结构化、过滤、过期、阈值、身份等级、日志、进程内可调用。"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.generated import Chunk, Document, DocumentVersion, RetrievalLog
from app.services import knowledge_embedding, knowledge_governance, knowledge_retrieval
from tests.conftest import auth, new_key, staff_token

REQUIRED_HIT_KEYS = {
    "source_type", "chunk_id", "document_id", "document_pk", "version",
    "chunk_ord", "title_path", "line_start", "line_end", "snippet",
}


def _publish_probe(client, token, *, category: str, content: str):
    suffix = uuid.uuid4().hex[:8]
    document_id = f"KB-RET-{suffix}"
    payload = (
        "---\n"
        f"document_id: {document_id}\n"
        f"title: 检索探针 {suffix}\n"
        f"category: {category}\n"
        'version: "1.0"\n'
        'effective_date: "2026-01-01"\n'
        "owner: 测试\n"
        "status: ACTIVE\n"
        "---\n"
        f"# 探针\n\n{content}\n"
    ).encode("utf-8")
    files = [("files", (f"{document_id}.md", payload, "text/markdown"))]
    assert client.post("/api/v1/knowledge/import/jobs", headers=auth(token, new_key()),
                       files=files).status_code == 200
    with SessionLocal() as db:
        document = db.execute(select(Document).where(Document.document_id == document_id)).scalar_one()
        version = db.execute(
            select(DocumentVersion).where(DocumentVersion.document_pk == document.id)
        ).scalar_one()
    knowledge_embedding.run_once(db=None, batch_size=1) if False else None
    with SessionLocal() as db:
        knowledge_embedding.run_once(db, batch_size=64)
    published = client.post(f"/api/v1/knowledge/versions/{version.id}/publish",
                            headers=auth(token, new_key()), json={"change_summary": "探针发布"})
    assert published.status_code == 200, published.text
    return document.id, version.id, document_id


def _search(client, token, query, **kwargs):
    body = {"query": query, "top_k": kwargs.pop("top_k", 10)}
    body.update(kwargs)
    return client.post("/api/v1/knowledge/retrieval/test", headers=auth(token, new_key()), json=body)


def test_hits_are_structured_and_score_free(client):
    token = staff_token(client)
    category = f"probe_cat_{uuid.uuid4().hex[:6]}"
    _, _, document_id = _publish_probe(
        client, token, category=category,
        content="门锁电池续航说明：8 节 5 号电池约可用 12 个月。",
    )
    response = _search(client, token, "门锁电池续航", filters={"category": category})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["hits"], body
    hit = body["hits"][0]
    assert set(hit) >= REQUIRED_HIT_KEYS
    assert hit["source_type"] == "chunk"
    assert hit["document_id"] == document_id
    assert isinstance(hit["line_start"], int) and isinstance(hit["line_end"], int)
    assert not any(key.endswith("_score") for key in hit)
    debug = body["debug"]
    assert {"vector_score", "text_score", "fused_score", "latency_ms"} <= set(debug)


def test_category_filter_is_enforced(client):
    token = staff_token(client)
    category = f"probe_cat_{uuid.uuid4().hex[:6]}"
    _publish_probe(client, token, category=category, content="摄像头异常发热需要断电冷却。")
    hit = _search(client, token, "摄像头异常发热", filters={"category": category})
    assert hit.json()["hits"]
    miss = _search(client, token, "摄像头异常发热", filters={"category": "不存在的类目"})
    assert miss.json()["hits"] == []


def test_expired_version_is_not_returned(client):
    token = staff_token(client)
    category = f"probe_cat_{uuid.uuid4().hex[:6]}"
    _, version_id, _ = _publish_probe(client, token, category=category,
                                      content="过期探针内容：滤网清洗周期为两周。")
    assert _search(client, token, "滤网清洗周期", filters={"category": category}).json()["hits"]
    with SessionLocal() as db:
        version = db.get(DocumentVersion, version_id)
        version.effective_until = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
    assert _search(client, token, "滤网清洗周期", filters={"category": category}).json()["hits"] == []


def test_identity_level_filters_and_can_be_proven(client):
    token = staff_token(client)
    category = f"probe_cat_{uuid.uuid4().hex[:6]}"
    _, version_id, _ = _publish_probe(client, token, category=category,
                                      content="身份等级探针：远程开锁操作规范。")
    with SessionLocal() as db:
        db.add(Chunk(
            tenant_id=1,
            document_version_id=version_id,
            ord=999,
            title_path="身份等级探针 / 客服专属",
            content="身份等级探针：远程开锁操作规范（客服专属条款）。",
            token_count=20,
            embedding_status="READY",
            identity_level="agent",
            metadata_json={"source_line_start": 1, "source_line_end": 1},
        ))
        db.commit()
    public = _search(client, token, "身份等级探针 远程开锁", filters={"category": category})
    assert all(hit["chunk_ord"] != 999 for hit in public.json()["hits"])
    agent = _search(client, token, "身份等级探针 远程开锁",
                    filters={"category": category}, identity_level="agent")
    assert any(hit["chunk_ord"] == 999 for hit in agent.json()["hits"])


def test_unrelated_query_returns_few_or_no_hits(client):
    token = staff_token(client)
    response = _search(client, token, "zzqqxx 无关查询 12345")
    assert response.status_code == 200
    assert len(response.json()["hits"]) <= 3


def test_retrieval_writes_log(client):
    token = staff_token(client)
    with SessionLocal() as db:
        before = len(db.execute(select(RetrievalLog)).scalars().all())
    _search(client, token, "门锁电池")
    with SessionLocal() as db:
        rows = db.execute(select(RetrievalLog)).scalars().all()
    assert len(rows) == before + 1
    assert rows[-1].query == "门锁电池"
    assert rows[-1].kind == "TEST"
    assert rows[-1].top_k == 10


def test_service_is_callable_in_process(client):
    token = staff_token(client)
    category = f"probe_cat_{uuid.uuid4().hex[:6]}"
    _publish_probe(client, token, category=category, content="进程内调用探针：安装前需断电。")
    with SessionLocal() as db:
        result = knowledge_retrieval.search(
            db, "安装前需断电", filters={"category": category}, top_k=5,
            actor={"id": 1, "party": "STAFF", "channel_ids": None},
        )
    assert result["hits"]
    assert set(result["hits"][0]) >= REQUIRED_HIT_KEYS
