#!/usr/bin/env python3
"""按 id 分批重算切片向量；可断点续跑（换模型、修复历史数据时使用）。

用法：
  python scripts/reindex_embeddings.py                        # 只补 PENDING / FAILED
  python scripts/reindex_embeddings.py --force                # 所有切片全部重算
  python scripts/reindex_embeddings.py --batch 200 --start-id 5000   # 从指定 id 续跑
"""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.integrations import embedding
from app.models.generated import Chunk
from app.services import knowledge_embedding


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=200)
    parser.add_argument("--start-id", type=int, default=0)
    parser.add_argument("--force", action="store_true", help="连 READY 一起重算")
    args = parser.parse_args()

    total = ready = failed = 0
    last_id = args.start_id
    while True:
        with SessionLocal() as db:
            statement = select(Chunk).where(Chunk.id > last_id).order_by(Chunk.id).limit(args.batch)
            if not args.force:
                statement = select(Chunk).where(
                    Chunk.id > last_id, Chunk.embedding_status != "READY"
                ).order_by(Chunk.id).limit(args.batch)
            chunks = list(db.execute(statement).scalars().all())
            if not chunks:
                break
            for chunk in chunks:
                last_id = chunk.id
            texts = [chunk.content for chunk in chunks]
            try:
                vectors = embedding.encode_documents(texts)
            except Exception as exc:  # noqa: BLE001 - 逐条兜底，坏数据不阻塞整批
                print(f"batch_failed id>{last_id}: {exc}", file=sys.stderr)
                vectors = []
                for chunk in chunks:
                    try:
                        vectors.append(embedding.encode_documents([chunk.content])[0])
                    except Exception:  # noqa: BLE001
                        knowledge_embedding._mark_failed(chunk, "reindex failed")
                        vectors.append(None)
            for chunk, vector in zip(chunks, vectors, strict=False):
                if vector is None:
                    failed += 1
                    continue
                knowledge_embedding._mark_ready(chunk, vector)
                ready += 1
            total += len(chunks)
            db.commit()
        print(f"progress id={last_id} total={total} ready={ready} failed={failed}", flush=True)

    with SessionLocal() as db:
        print(f"done total={total} ready={ready} failed={failed} stats={knowledge_embedding.stats(db)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
