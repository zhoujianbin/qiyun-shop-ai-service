"""清理智能客服遗留数据：断流占位、无标题孤儿会话、评测遗留的待确认动作。

用法：
    python scripts/cleanup_assistant.py            # 只报告
    python scripts/cleanup_assistant.py --apply    # 真删
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402

ORPHAN_SQL = """
select c.id, c.created_at, m.id as message_id
from assistant.conversation c
join assistant.message m on m.conversation_id = c.id
where m.role = 'ASSISTANT' and m.status = 'STREAMING' and coalesce(m.content, '') = ''
  and (select count(*) from assistant.message x where x.conversation_id = c.id) = 1
order by c.id
"""
STALE_SQL = """
select id, conversation_id, updated_at from assistant.message
where status = 'STREAMING' and updated_at < now() - interval '10 minutes'
order by id
"""
TITLE_SQL = """
select id from assistant.conversation
where (title is null or title = '') and exists (
    select 1 from assistant.message m
    where m.conversation_id = assistant.conversation.id and m.role = 'USER')
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="真正执行删除/更新")
    args = parser.parse_args()
    with SessionLocal() as db:
        orphans = db.execute(text(ORPHAN_SQL)).fetchall()
        stale = db.execute(text(STALE_SQL)).fetchall()
        untitled = db.execute(text(TITLE_SQL)).fetchall()
        print(f"孤儿会话（只有一条空 STREAMING 消息）: {len(orphans)} -> {[r[0] for r in orphans][:20]}")
        print(f"超时 STREAMING 消息: {len(stale)}")
        print(f"有用户消息但无标题的会话: {len(untitled)}")
        if not args.apply:
            print("（只报告；加 --apply 执行清理）")
            return 0
        for row in stale:
            db.execute(text("update assistant.message set status='FAILED',"
                            " metadata = coalesce(metadata, '{}'::jsonb) || '{\"error_code\":\"STALE_STREAM\"}'::jsonb"
                            " where id = :id"), {"id": row[0]})
        for row in untitled:
            db.execute(text("""
                update assistant.conversation c set title = sub.q
                from (select conversation_id, left(content, 30) as q from assistant.message
                      where conversation_id = :id and role = 'USER' order by id limit 1) sub
                where c.id = sub.conversation_id
            """), {"id": row[0]})
        orphan_ids = [row[0] for row in orphans]
        if orphan_ids:
            db.execute(text("delete from assistant.message where conversation_id = any(:ids)"),
                       {"ids": orphan_ids})
            db.execute(text("delete from assistant.pending_action where conversation_id = any(:ids)"),
                       {"ids": orphan_ids})
            db.execute(text("delete from assistant.conversation where id = any(:ids)"),
                       {"ids": orphan_ids})
        db.commit()
        print(f"已清理：删除孤儿会话 {len(orphan_ids)}，修复超时消息 {len(stale)}，补标题 {len(untitled)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
