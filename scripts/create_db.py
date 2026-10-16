#!/usr/bin/env python3
"""创建（或重建）数据库并应用 db/schema.sql。

用法：
  python scripts/create_db.py                    # 使用 DATABASE_URL 指向的库
  python scripts/create_db.py --db qiyun_shop_test --reset
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
    parser.add_argument("--db", default=None)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    parts = split_dsn(settings.database_url)
    target = args.db or parts["db"]
    admin = f"postgresql://{parts['user']}:{parts['pw']}@{parts['host']}:{parts['port']}/{parts['db']}"
    if parts["db"] == target and not args.reset:
        print(f"目标库 {target} 已存在；如需重建请加 --reset")
    with psycopg.connect(admin, autocommit=True) as conn:
        with conn.cursor() as cur:
            if parts["db"] == target:
                raise SystemExit("DATABASE_URL 指向的库与目标库相同；请通过 --db 指定新库名，避免误删")
            cur.execute("select 1 from pg_database where datname = %s", (target,))
            exists = cur.fetchone() is not None
            if exists and not args.reset:
                print(f"数据库 {target} 已存在，跳过创建")
            else:
                if exists:
                    cur.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname = %s", (target,))
                    cur.execute(f'DROP DATABASE IF EXISTS "{target}"')
                    print(f"已删除旧库 {target}")
                cur.execute(f'CREATE DATABASE "{target}"')
                print(f"已创建数据库 {target}")
    target_dsn = f"postgresql://{parts['user']}:{parts['pw']}@{parts['host']}:{parts['port']}/{target}"
    sql = SCHEMA.read_text(encoding="utf-8")
    with psycopg.connect(target_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    with psycopg.connect(target_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) from pg_tables where schemaname in ('shared','commerce','knowledge')")
            print(f"schema 应用完成，表数量：{cur.fetchone()[0]}")


if __name__ == "__main__":
    main()
