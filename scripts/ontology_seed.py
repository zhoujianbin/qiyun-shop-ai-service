#!/usr/bin/env python3
"""四期本体种子：结构化规则导入 → 文档候选抽取 → 审核结论落库 → （可选）切片回填。

用法：
  python scripts/ontology_seed.py                      # 导入 + 抽取 + 审核结论，不自动通过
  python scripts/ontology_seed.py --auto-approve       # 额外把 DRAFT 实体审核通过（演示/测试用）
  python scripts/ontology_seed.py --with-backfill      # 额外回填 chunk_entity
  python scripts/ontology_seed.py --db qiyun_shop_dev_3

幂等：重复执行不产生重复实体/关系/映射。
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.services import ontology, ontology_extract, ontology_review  # noqa: E402

ACTOR = {"id": None, "party": "SYSTEM", "label": "ontology_seed.py"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-approve", action="store_true", help="把 DRAFT 实体批量审核通过")
    parser.add_argument("--with-backfill", action="store_true", help="回填 ontology.chunk_entity")
    parser.add_argument("--json", action="store_true", help="输出 JSON 摘要")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        imported = ontology.import_structured_rules(db, ACTOR)
        extracted = ontology_extract.extract_candidates(db, ACTOR)
        reviewed = ontology_review.apply_review(db, ACTOR)
        approved = 0
        if args.auto_approve:
            ids = [row[0] for row in db.execute(
                text("select id from ontology.entity where status = 'DRAFT'")).fetchall()]
            if ids:
                approved = ontology.review(db, ACTOR, entity_ids=ids, action="approve")["updated"]
                fault_ids = [row[0] for row in db.execute(
                    text("select id from ontology.entity where kind = 'fault'")).fetchall()]
                ontology.review(db, ACTOR, entity_ids=fault_ids, action="approve")
        backfilled = ontology.backfill_chunk_entities(db, ACTOR) if args.with_backfill else None

        summary = {
            "import": {k: imported[k] for k in ("total_entity", "total_relation")},
            "extract": {k: extracted[k] for k in ("total_entity", "total_relation",
                                                  "symptom_new", "relation_new")},
            "review_ai": reviewed,
            "approved": approved,
            "backfill": backfilled,
        }
        summary["by_predicate"] = {row[0]: row[1] for row in db.execute(text(
            "select predicate, count(*) from ontology.relation where status = 'APPROVED'"
            " group by predicate order by predicate")).fetchall()}
        summary["by_kind"] = {row[0]: row[1] for row in db.execute(text(
            "select kind, count(*) from ontology.entity where status = 'APPROVED'"
            " group by kind order by kind")).fetchall()}
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=1))
        else:
            for key, value in summary.items():
                print(key, ":", value)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
