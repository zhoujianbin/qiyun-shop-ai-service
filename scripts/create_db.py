#!/usr/bin/env python3
"""创建（或重建）数据库并应用 db/schema.sql。

用法：
  python scripts/create_db.py                              # 使用 DATABASE_URL 指向的库
  python scripts/create_db.py --db qiyun_shop_dev_li       # 创建你自己的库（共用实例推荐）
  python scripts/create_db.py --db qiyun_shop_dev --reset --force   # 重建（危险，需显式确认）
"""
import argparse
import pathlib
import re
import sys

import psycopg

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402

SCHEMA = ROOT / "db" / "schema.sql"


def split_dsn(url: str) -> dict:
    m = re.match(r"postgresql\+psycopg://(?P<user>[^:]+):(?P<pw>[^@]*)@(?P<host>[^:/]+):(?P<port>\d+)/(?P<db>.+)", url)
    if not m:
        raise SystemExit(f"无法解析 DATABASE_URL: {url}")
    return m.groupdict()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=None, help="目标库名，默认取 DATABASE_URL 中的库名")
    parser.add_argument("--reset", action="store_true", help="删除并重建目标库（危险）")
    parser.add_argument("--force", action="store_true", help="与 --reset 同用，确认删除已存在的目标库")
    args = parser.parse_args()
    parts = split_dsn(settings.database_url)
    target = args.db or parts["db"]

    def dsn(db: str) -> str:
        return f"postgresql://{parts['user']}:{parts['pw']}@{parts['host']}:{parts['port']}/{db}"

    # 目标库可能尚不存在，维护连接优先连 postgres 库
    try:
        admin = psycopg.connect(dsn("postgres"), autocommit=True)
    except psycopg.OperationalError:
        admin = psycopg.connect(dsn(parts["db"]), autocommit=True)

    with admin:
        with admin.cursor() as cur:
            cur.execute("select 1 from pg_database where datname = %s", (target,))
            exists = cur.fetchone() is not None
            if exists and args.reset and not args.force:
                raise SystemExit(
                    f"目标库 {target} 已存在。共用 PostgreSQL 实例时 --reset 会删除该库的全部数据；"
                    " 确认只重建你自己的库请追加 --force，或改用你自己的库名：--db qiyun_shop_dev_<你的名字>"
                )
            if exists and not args.reset:
                print(f"数据库 {target} 已存在，跳过创建；如需重建请加 --reset --force")
            else:
                if exists:
                    cur.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname = %s", (target,))
                    cur.execute(f'DROP DATABASE IF EXISTS "{target}"')
                    print(f"已删除旧库 {target}")
                cur.execute(f'CREATE DATABASE "{target}"')
                print(f"已创建数据库 {target}")

    sql = SCHEMA.read_text(encoding="utf-8")
    with psycopg.connect(dsn(target), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    with psycopg.connect(dsn(target)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select count(*) from pg_tables where schemaname in ('shared','commerce','knowledge','assistant')"
            )
            print(f"schema 应用完成，表数量：{cur.fetchone()[0]}")


if __name__ == "__main__":
    main()
