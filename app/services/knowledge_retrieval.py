"""混合检索：过滤 -> 全文 + 向量双路召回 -> RRF 融合 -> 稳定引用 + 调试段。

对外只有一个入口 `search()`：路由只做参数校验、权限与日志；三期的图节点可直接 import。
返回结构：
  {"hits": [ {document_id, version, title_path, line_start, line_end, chunk_ord, chunk_id, snippet} ],
   "debug": {"vector_score": {...}, "text_score": {...}, "fused_score": {...}, "latency_ms": n}}
`hits` 是稳定引用契约（不含分数）；分数只在 `debug` 里，仅供调试。
"""
from __future__ import annotations

import time

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services import audit

RRF_K = 60
SIMILARITY_THRESHOLD = 0.35
TEXT_SIMILARITY_FLOOR = 0.15
IDENTITY_LEVELS = {
    "public": ["public"],
    "customer": ["public", "customer"],
    "agent": ["public", "customer", "agent"],
}


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"


def _channel_codes(db: Session, actor: dict) -> list[str] | None:
    """把 actor 的渠道 id 换成渠道编码；None 表示可见全部渠道。"""
    ids = (actor or {}).get("channel_ids")
    if ids is None:
        return None
    if not ids:
        return []
    from app.models import ChannelAccount

    rows = db.execute(
        select(ChannelAccount.code).where(ChannelAccount.id.in_(ids))
    ).scalars().all()
    return list(rows)


def _filters_sql(filters: dict, channel_codes: list[str] | None, identity_level: str):
    """返回 (SQL 片段列表, 参数字典)。"""
    clauses = [
        "ch.tenant_id = :tenant_id",
        "dv.status = 'ACTIVE'",
        "(dv.effective_until IS NULL OR dv.effective_until > now())",
        "ch.embedding_status = 'READY'",
        "ch.identity_level = ANY(:identity_levels)",
    ]
    params: dict = {
        "tenant_id": settings.tenant_id,
        "identity_levels": IDENTITY_LEVELS.get(identity_level, IDENTITY_LEVELS["public"]),
    }
    if filters.get("category"):
        clauses.append("d.category = :category")
        params["category"] = filters["category"]
    if filters.get("product_scope"):
        clauses.append("d.product_scope = :product_scope")
        params["product_scope"] = filters["product_scope"]
    if channel_codes is not None:
        if not channel_codes:
            clauses.append("false")  # 没有任何可见渠道
        else:
            clauses.append("(d.channel_scope = '[]'::jsonb OR d.channel_scope ?| :channel_codes)")
            params["channel_codes"] = channel_codes
    return clauses, params


BASE_SELECT = """
SELECT ch.id AS chunk_id,
       ch.ord AS chunk_ord,
       ch.content AS content,
       ch.title_path AS title_path,
       (ch.metadata->>'source_line_start')::int AS line_start,
       (ch.metadata->>'source_line_end')::int AS line_end,
       dv.version AS version,
       d.document_id AS document_id,
       d.id AS document_pk
FROM knowledge.chunk ch
JOIN knowledge.document_version dv ON dv.id = ch.document_version_id
JOIN knowledge.document d ON d.id = dv.document_pk
"""


def search(
    db: Session,
    query: str,
    *,
    filters: dict | None = None,
    top_k: int = 10,
    actor: dict | None = None,
    identity_level: str = "public",
) -> dict:
    query = (query or "").strip()
    if not query:
        return {"hits": [], "debug": {"vector_score": {}, "text_score": {}, "fused_score": {},
                                      "latency_ms": 0, "candidates": 0}}
    started = time.monotonic()
    filters = filters or {}
    channel_codes = _channel_codes(db, actor or {})
    clauses, params = _filters_sql(filters, channel_codes, identity_level)
    where = " AND ".join(clauses)
    candidates = max(top_k * 4, 20)

    from app.integrations import embedding

    vector = _vector_literal(embedding.encode_query(query))
    vector_rows = db.execute(text(
        BASE_SELECT
        + f" WHERE {where} AND ch.embedding IS NOT NULL"
        + " ORDER BY ch.embedding <=> (:vector)::vector LIMIT :limit"
    ), {**params, "vector": vector, "limit": candidates}).mappings().all()
    vector_scores = {
        row["chunk_id"]: float(row["score"] or 0.0)
        for row in db.execute(text(
            "SELECT ch.id AS chunk_id, 1 - (ch.embedding <=> (:vector)::vector) AS score"
            f" FROM knowledge.chunk ch JOIN knowledge.document_version dv ON dv.id = ch.document_version_id"
            f" JOIN knowledge.document d ON d.id = dv.document_pk WHERE {where}"
            " AND ch.id = ANY(:ids)"
        ), {**params, "vector": vector, "ids": [row["chunk_id"] for row in vector_rows] or [0]}).mappings().all()
    } if vector_rows else {}

    text_rows = db.execute(text(
        BASE_SELECT
        + f" WHERE {where}"
        + " AND (ch.tsv @@ plainto_tsquery('simple', :query) OR similarity(ch.content, :query) >= :floor)"
        + " ORDER BY ts_rank(ch.tsv, plainto_tsquery('simple', :query)) DESC,"
        + " similarity(ch.content, :query) DESC LIMIT :limit"
    ), {**params, "query": query, "floor": TEXT_SIMILARITY_FLOOR, "limit": candidates}).mappings().all()

    text_scores: dict[int, float] = {}
    if text_rows:
        for row in db.execute(text(
            "SELECT ch.id AS chunk_id, similarity(ch.content, :query) AS score"  # trgm 兜底
            " FROM knowledge.chunk ch WHERE ch.id = ANY(:ids)"
        ), {"query": query, "ids": [row["chunk_id"] for row in text_rows]}).mappings().all():
            text_scores[row["chunk_id"]] = float(row["score"])

    # 向量路：低于阈值直接丢弃，不为凑满 TopK 返回低相关
    vector_ranked = [row["chunk_id"] for row in vector_rows
                     if vector_scores.get(row["chunk_id"], 0.0) >= SIMILARITY_THRESHOLD]
    text_ranked = [row["chunk_id"] for row in text_rows]

    fused: dict[int, float] = {}
    for rank, chunk_id in enumerate(vector_ranked):
        fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
    for rank, chunk_id in enumerate(text_ranked):
        fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)

    by_id = {row["chunk_id"]: row for row in list(vector_rows) + list(text_rows)}
    ordered = sorted(fused.items(), key=lambda item: item[1], reverse=True)[:top_k]

    hits = []
    for chunk_id, _ in ordered:
        row = by_id[chunk_id]
        snippet = (row["content"] or "").strip().replace("\n", " ")
        hits.append({
            "source_type": "chunk",
            "chunk_id": chunk_id,
            "document_id": row["document_id"],
            "document_pk": row["document_pk"],
            "version": row["version"],
            "chunk_ord": row["chunk_ord"],
            "title_path": row["title_path"] or "",
            "line_start": row["line_start"],
            "line_end": row["line_end"],
            "snippet": snippet[:200],
        })

    latency_ms = int((time.monotonic() - started) * 1000)
    return {
        "hits": hits,
        "debug": {
            "vector_score": {str(k): round(v, 4) for k, v in vector_scores.items()},
            "text_score": {str(k): round(v, 4) for k, v in text_scores.items()},
            "fused_score": {str(k): round(v, 6) for k, v in fused.items()},
            "latency_ms": latency_ms,
            "candidates": len(by_id),
        },
    }


def log_search(db: Session, actor: dict, query: str, filters: dict, top_k: int, result: dict,
               identity_level: str = "public", kind: str = "TEST") -> None:
    from app.models.generated import RetrievalLog

    db.add(RetrievalLog(
        tenant_id=settings.tenant_id,
        query=query,
        filters=filters or {},
        top_k=top_k,
        hit_count=len(result["hits"]),
        hits=result["hits"],
        latency_ms=result["debug"]["latency_ms"],
        actor_id=(actor or {}).get("id"),
        identity_level=identity_level,
        kind=kind,
    ))
    audit.record(db, actor, "knowledge.retrieval.test", "knowledge.chunk", None,
                 after={"query": query, "hits": len(result["hits"]), "top_k": top_k})
