#!/usr/bin/env python3
"""三期会话清理：删除超保留期的已关闭会话（级联 6 张表）并把僵尸 STREAMING 置 FAILED。

用法：
  python scripts/assistant_cleanup.py                 # 按 ASSISTANT_RETENTION_DAYS 清理
  python scripts/assistant_cleanup.py --days 30       # 覆盖保留期
  python scripts/assistant_cleanup.py --dry-run       # 只统计不删除
"""
import argparse
import pathlib
import sys
from datetime import timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, func, select, update  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.models.generated import Conversation, Message  # noqa: E402
from app.services.common import now  # noqa: E402

STREAMING_STALE_MINUTES = 2


def purge_stale_streaming(db, *, dry_run: bool = False) -> int:
    cutoff = now() - timedelta(minutes=STREAMING_STALE_MINUTES)
    statement = select(Message).where(Message.status == "STREAMING", Message.updated_at < cutoff)
    rows = db.execute(statement).scalars().all()
    if not dry_run:
        db.execute(
            update(Message)
            .where(Message.status == "STREAMING", Message.updated_at < cutoff)
            .values(status="FAILED")
        )
    return len(rows)


def purge_empty_conversations(db, *, hours: int = 1, dry_run: bool = False) -> int:
    """删除从未产生消息的空会话（用户建了却没提问）。"""
    cutoff = now() - timedelta(hours=hours)
    ids = db.execute(
        select(Conversation.id).where(
            Conversation.message_count == 0, Conversation.created_at < cutoff
        )
    ).scalars().all()
    if not dry_run and ids:
        db.execute(delete(Conversation).where(Conversation.id.in_(ids)))
    return len(ids)


def purge_closed_conversations(db, *, days: int, dry_run: bool = False) -> int:
    cutoff = now() - timedelta(days=days)
    # 用 last_message_at 而不是 updated_at：后者被 tg_touch_updated_at 触发器维护，
    # 任何更新都会刷新，不能作为"最后活动时间"的判据。
    ids = db.execute(
        select(Conversation.id).where(
            Conversation.status == "CLOSED",
            func.coalesce(Conversation.last_message_at, Conversation.created_at) < cutoff,
        )
    ).scalars().all()
    if not dry_run and ids:
        db.execute(delete(Conversation).where(Conversation.id.in_(ids)))
    return len(ids)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    days = args.days or settings.assistant_retention_days

    with SessionLocal() as db:
        stale = purge_stale_streaming(db, dry_run=args.dry_run)
        empty = purge_empty_conversations(db, dry_run=args.dry_run)
        removed = purge_closed_conversations(db, days=days, dry_run=args.dry_run)
        if not args.dry_run:
            db.commit()
    print(f"stale_streaming={stale} empty_conversations={empty} closed_conversations={removed} "
          f"days={days} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
