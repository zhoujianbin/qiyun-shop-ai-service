#!/usr/bin/env python3
"""本体链路演示：一条客服问题 → 实体归一 → 图遍历 → 带范围检索。

用法：
  python scripts/ontology_demo.py "指纹识别差，还在保修吗"
  python scripts/ontology_demo.py "电池鼓包了怎么办" --top-k 3

只跑确定性部分（不调大模型），用来解释本体到底在哪一步起作用。
"""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.db import SessionLocal
from app.services import knowledge_retrieval, ontology


def show_graph(db, entity_id: int, scope: str | None, depth: int = 2) -> None:
    g = ontology.graph(db, entity_id, depth=depth, product_scope=scope)
    label = f"scope={scope}" if scope else "不限范围"
    print(f"  图遍历（{label}，depth={depth}）：")
    for node in g["nodes"]:
        entity = node["entity"]
        print(f"    {'  ' * (node['depth'] - 1)}-{node['via']}-> {entity['code']}"
              f"（{entity['kind']}）{entity['name']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    with SessionLocal() as db:
        result = ontology.normalize_question(db, args.question)
        print(f"问题：{args.question}")
        print("① 归一：", [(item["code"], item["kind"], item["matched"]) for item in result["entities"]]
              or "零命中，退化为原样检索")
        print("   产品范围：", result["product_scope"] or "不收窄")
        if not result["entities"]:
            return 0

        root = result["entities"][0]
        print(f"\n② 关系（以 {root['code']} 为起点）：")
        show_graph(db, root["id"], None)
        if result["product_scope"]:
            show_graph(db, root["id"], result["product_scope"])

        print("\n③ 检索对比：")
        base = knowledge_retrieval.search(db, args.question, top_k=args.top_k, actor={})
        scoped = knowledge_retrieval.search(
            db, args.question, top_k=args.top_k, actor={},
            filters={"product_scope": result["product_scope"]} if result["product_scope"] else None)
        for title, hits in (("不带本体过滤", base["hits"]), ("带本体过滤", scoped["hits"])):
            print(f"  {title}：")
            for hit in hits:
                tags = [e.code for e in ontology.entities_of_chunk(
                    db, hit["document_id"], hit["version"], hit["chunk_ord"])]
                print(f"    {hit['document_id']:<22}{hit['title_path'][:38]:<40}{tags}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
