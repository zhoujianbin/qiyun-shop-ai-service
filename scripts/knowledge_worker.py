#!/usr/bin/env python3
"""知识库后台 worker：补齐切片向量（定时生效在组 5 接入同一进程）。

用法：
  python scripts/knowledge_worker.py --once              # 跑一轮就退出（验收用）
  python scripts/knowledge_worker.py --interval 30       # 常驻，每 30 秒一轮
  python scripts/knowledge_worker.py --retry-failed      # 把 FAILED 切片放回队列
"""
import argparse
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.db import SessionLocal  # noqa: E402
from app.services import knowledge_embedding, knowledge_governance, knowledge_import


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="跑一轮后退出")
    parser.add_argument("--interval", type=float, default=30.0, help="常驻模式下的轮询间隔（秒）")
    parser.add_argument("--batch", type=int, default=64, help="每批处理的切片数")
    parser.add_argument("--max-batches", type=int, default=10000)
    parser.add_argument("--retry-failed", action="store_true", help="先把失败切片放回待处理")
    args = parser.parse_args()

    if args.retry_failed:
        with SessionLocal() as db:
            count = knowledge_import.requeue_failed_chunks(db)
            db.commit()
        print(f"requeued_failed={count}")

    if args.once:
        with SessionLocal() as db:
            scheduled = knowledge_governance.activate_due(db)
            db.commit()
        with SessionLocal() as db:
            result = knowledge_embedding.run_once(
                db, batch_size=args.batch, max_batches=args.max_batches
            )
        print(f"once scheduled={scheduled} embedding={result}")
        return 0

    try:
        while True:
            with SessionLocal() as db:
                scheduled = knowledge_governance.activate_due(db)
                db.commit()
            with SessionLocal() as db:
                result = knowledge_embedding.run_once(db, batch_size=args.batch)
            print(f"tick scheduled={scheduled} embedding={result}", flush=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
