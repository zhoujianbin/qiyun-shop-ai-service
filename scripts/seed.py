#!/usr/bin/env python3
"""生成栖云智家一期测试数据（企业基础 + 知识库商品 + 客户 + 订单 + 售后）。

用法：
  python scripts/create_db.py --db qiyun_shop_dev --reset   # 建库并应用 schema
  python scripts/seed.py --orders 60                        # 生成测试数据
"""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.db import SessionLocal  # noqa: E402
from scripts import bootstrap, generate_orders  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-orders", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        print("reference:", bootstrap.bootstrap_reference(db))
        print("catalog  :", bootstrap.bootstrap_catalog(db))
        print("customers:", bootstrap.bootstrap_customers(db))
        if not args.skip_orders:
            result = generate_orders.generate(db, count=args.orders, seed=args.seed)
            print("orders   :", result["by_plan"], "total", result["orders"])
            print("backdated:", generate_orders.backdate(db, result["order_ids"]))
        from sqlalchemy import func, select

        from app.models import AppUser, Inventory, Order, Product, Refund, Sku

        print("summary  : products=%s skus=%s users=%s orders=%s inventory_rows=%s refunds=%s" % (
            db.execute(select(func.count()).select_from(Product)).scalar_one(),
            db.execute(select(func.count()).select_from(Sku)).scalar_one(),
            db.execute(select(func.count()).select_from(AppUser)).scalar_one(),
            db.execute(select(func.count()).select_from(Order)).scalar_one(),
            db.execute(select(func.count()).select_from(Inventory)).scalar_one(),
            db.execute(select(func.count()).select_from(Refund)).scalar_one(),
        ))


if __name__ == "__main__":
    main()
