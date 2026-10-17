"""向量化流水线：把待处理切片补齐为就绪，供 worker 与重算脚本共用。

状态机：PENDING -> READY；异常 -> FAILED（metadata.embedding_attempts 累加）。
检索只使用 READY。批内失败会退化为逐条处理，避免一条坏数据连坐整批。
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.integrations import embedding
from app.models.generated import Chunk

MAX_ATTEMPTS = 3


def _mark_failed(chunk: Chunk, error: str | None = None) -> None:
    chunk.embedding_status = "FAILED"
    meta = dict(chunk.metadata_json or {})
    meta["embedding_attempts"] = int(meta.get("embedding_attempts", 0)) + 1
    if error:
        meta["embedding_error"] = str(error)[:500]
    chunk.metadata_json = meta


def _mark_ready(chunk: Chunk, vector: list[float]) -> None:
    chunk.embedding = vector
    chunk.embedding_status = "READY"
    meta = dict(chunk.metadata_json or {})
    meta.pop("embedding_error", None)
    chunk.metadata_json = meta


def claim_pending(db: Session, limit: int) -> list[Chunk]:
    """取待处理切片并加锁，多个 worker 并发时由 SKIP LOCKED 互斥。"""
    statement = (
        select(Chunk)
        .where(Chunk.embedding_status == "PENDING")
        .order_by(Chunk.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list(db.execute(statement).scalars().all())


def embed_chunks(db: Session, chunks: list[Chunk]) -> dict:
    if not chunks:
        return {"ready": 0, "failed": 0}
    try:
        vectors = embedding.encode_documents([chunk.content for chunk in chunks])
    except Exception as exc:  # noqa: BLE001 - 批失败退化为逐条，定位坏数据
        ready = failed = 0
        for chunk in chunks:
            try:
                vector = embedding.encode_documents([chunk.content])[0]
            except Exception as inner:  # noqa: BLE001
                _mark_failed(chunk, str(inner))
                failed += 1
            else:
                _mark_ready(chunk, vector)
                ready += 1
        db.flush()
        if failed and not ready:
            raise RuntimeError(f"整批向量化失败：{exc}") from exc
        return {"ready": ready, "failed": failed}
    for chunk, vector in zip(chunks, vectors, strict=True):
        _mark_ready(chunk, vector)
    db.flush()
    return {"ready": len(chunks), "failed": 0}


def run_once(db: Session, *, batch_size: int = 64, max_batches: int = 10_000) -> dict:
    """跑一轮：直到没有待处理切片或达到批次数上限。"""
    total_ready = total_failed = batches = 0
    while batches < max_batches:
        chunks = claim_pending(db, batch_size)
        if not chunks:
            break
        result = embed_chunks(db, chunks)
        total_ready += result["ready"]
        total_failed += result["failed"]
        batches += 1
    if total_ready:
        from app.services import audit
        audit.emit(db, "knowledge.chunk.embedded", "chunk", "batch", {"ready": total_ready})
    db.commit()
    return {"ready": total_ready, "failed": total_failed, "batches": batches}


def stats(db: Session) -> dict:
    rows = db.execute(
        select(Chunk.embedding_status, func.count()).group_by(Chunk.embedding_status)
    ).all()
    counts = {status: count for status, count in rows}
    for key in ("PENDING", "READY", "FAILED"):
        counts.setdefault(key, 0)
    return counts
