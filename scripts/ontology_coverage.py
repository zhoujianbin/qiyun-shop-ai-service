#!/usr/bin/env python3
"""本体对知识库文档的覆盖统计：按文档前缀给出已映射 / 未映射，用来决定下一批补哪里。

用法：
  python scripts/ontology_coverage.py                 # 按前缀汇总
  python scripts/ontology_coverage.py --uncovered 30  # 再列出前 30 篇未覆盖文档
  python scripts/ontology_coverage.py --json          # 机器可读

口径：knowledge.document 左连 ontology.chunk_entity（APPROVED），至少一条映射算已覆盖。
覆盖不等于正确：映射只说明该文档的切片被某个实体别名命中，仍需人工抽检。
"""
import argparse
import json
import pathlib
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.core.db import SessionLocal


def folder_of(document_id: str) -> str:
    """KB-SHIP-002 -> SHIP；SCN-014 -> SCN。"""
    parts = document_id.split("-")
    if len(parts) < 2:
        return document_id
    return "SCN" if parts[0] == "SCN" else parts[1]


def collect() -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(text("""
            SELECT d.document_id, d.title, count(ce.id) AS mapped
            FROM knowledge.document d
            LEFT JOIN ontology.chunk_entity ce
                   ON ce.document_id = d.document_id AND ce.status = 'APPROVED'
            GROUP BY d.document_id, d.title
            ORDER BY d.document_id
        """)).mappings().all()
    return [{"document_id": row["document_id"], "title": row["title"],
             "mapped": int(row["mapped"]), "folder": folder_of(row["document_id"])}
            for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--uncovered", type=int, default=0, metavar="N")
    args = parser.parse_args()

    docs = collect()
    if not docs:
        print("没有文档：先导入知识库")
        return 1

    groups: dict[str, dict] = defaultdict(lambda: {"docs": 0, "covered": 0})
    for doc in docs:
        item = groups[doc["folder"]]
        item["docs"] += 1
        if doc["mapped"] > 0:
            item["covered"] += 1

    total_docs = len(docs)
    total_covered = sum(1 for doc in docs if doc["mapped"] > 0)
    uncovered = [doc for doc in docs if doc["mapped"] == 0]

    if args.json:
        print(json.dumps({
            "documents": total_docs,
            "covered": total_covered,
            "ratio": round(total_covered / total_docs, 4),
            "folders": {name: {**item, "uncovered": item["docs"] - item["covered"]}
                        for name, item in sorted(groups.items())},
            "uncovered": uncovered,
        }, ensure_ascii=False, indent=1))
        return 0

    print(f"文档 {total_docs} 篇，已覆盖 {total_covered} 篇（{total_covered / total_docs:.1%}）")
    print(f"{'目录':<12}{'文档':>6}{'覆盖':>6}{'未覆盖':>8}")
    for name, item in sorted(groups.items(), key=lambda pair: (pair[1]["covered"] - pair[1]["docs"], pair[0])):
        print(f"{name:<12}{item['docs']:>6}{item['covered']:>6}{item['docs'] - item['covered']:>8}")

    if args.uncovered:
        print("\n未覆盖文档：")
        for doc in uncovered[:args.uncovered]:
            print(f"  {doc['document_id']:<18}{doc['title']}")
        if len(uncovered) > args.uncovered:
            print(f"  ... 其余 {len(uncovered) - args.uncovered} 篇用 --uncovered 调大查看")
    return 0


if __name__ == "__main__":
    sys.exit(main())
