#!/usr/bin/env python3
"""从 db/schema.sql 生成 SQLAlchemy 2.0 ORM 模型（DDL 为唯一事实源）。

用法：python scripts/gen_models.py
输出：app/models/generated.py

说明：解析 CREATE TABLE 的列定义，保留类型、主键与 DEFAULT（生成 server_default），
     这样未赋值的列由数据库默认值填充，避免插入 NULL 违反 NOT NULL 约束。
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
DDL = ROOT / "db" / "schema.sql"
OUT = ROOT / "app" / "models" / "generated.py"

TYPE_MAP = [
    (r"^bigint", "BigInteger"),
    (r"^smallint", "SmallInteger"),
    (r"^integer", "Integer"),
    (r"^int$", "Integer"),
    (r"^varchar\((\d+)\)", "String"),
    (r"^char\((\d+)\)", "String"),
    (r"^numeric\((\d+),(\d+)\)", "Numeric"),
    (r"^text$", "Text"),
    (r"^boolean$", "Boolean"),
    (r"^timestamptz$", "DateTime"),
    (r"^date$", "Date"),
    (r"^jsonb$", "JSONB"),
    (r"^inet$", "INET"),
    (r"^uuid$", "UUID"),
    (r"^interval$", "Interval"),
    (r"^vector\((\d+)\)", "Vector"),
]


# 与 SQLAlchemy Declarative 冲突的属性名：属性改名，列名保持不变
RESERVED_ATTRS = {"metadata": "metadata_json"}


def map_type(raw: str) -> str:
    raw = raw.strip().lower()
    if raw == "timestamptz":
        return "DateTime(timezone=True)"
    for pattern, name in TYPE_MAP:
        m = re.match(pattern, raw)
        if not m:
            continue
        args = ", ".join(a for a in m.groups() if a)
        return name + "(" + args + ")" if args else name
    print("WARN unmapped type:", raw)
    return "Text"


def split_top(body: str):
    parts, depth, cur = [], 0, ""
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return parts


def camel(name: str) -> str:
    if name == "orders":
        return "Order"
    return "".join(p.capitalize() for p in name.split("_"))


def default_expression(remainder: str) -> str:
    if re.search(r"\bIDENTITY\b", remainder, re.I):
        return ""
    m = re.search(r"\bDEFAULT\s+(.+)$", remainder, re.I | re.S)
    if not m:
        return ""
    expr = re.split(r"\s+(?:NOT\s+NULL|PRIMARY\s+KEY|REFERENCES|CHECK|UNIQUE|CONSTRAINT)\b", m.group(1), flags=re.I)[0]
    expr = expr.strip().rstrip(",").strip()
    if not expr:
        return ""
    return ", server_default=text(" + json.dumps(expr) + ")"


def main() -> None:
    ddl = DDL.read_text(encoding="utf-8")
    header = [
        '"""自动生成，请勿手工修改：改动 db/schema.sql 后执行 scripts/gen_models.py。"""',
        "from datetime import date, datetime",
        "from decimal import Decimal",
        "",
        "from sqlalchemy import (",
        "    BigInteger, Boolean, Date, DateTime, Integer, Interval, Numeric, SmallInteger, String, Text, text,",
        ")",
        "from pgvector.sqlalchemy import Vector",
        "from sqlalchemy.dialects.postgresql import INET, JSONB, UUID",
        "from sqlalchemy.orm import DeclarativeBase, mapped_column",
        "",
        "",
        "class Base(DeclarativeBase):",
        "    pass",
        "",
        "",
    ]
    blocks = []
    for m in re.finditer(r"CREATE TABLE\s+(\w+)\.(\w+)\s*\(", ddl):
        schema, table = m.group(1), m.group(2)
        if schema not in ("shared", "commerce", "knowledge", "assistant", "ontology"):
            continue
        start = m.end()
        depth, end = 1, start
        while depth > 0:
            ch = ddl[end]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            end += 1
        body = ddl[start:end - 1]
        pk_cols, cols = [], []
        for part in split_top(body):
            text_def = part.strip()
            if not text_def:
                continue
            upper = text_def.upper()
            if re.match(r"^(CONSTRAINT|FOREIGN\s+KEY|UNIQUE|CHECK)\b", upper):
                continue
            if "GENERATED ALWAYS AS" in upper:
                # 生成列由数据库计算，不映射（检索时用 SQL 表达式引用）
                continue
            if upper.startswith("PRIMARY KEY"):
                pk_cols = [a or b for a, b in re.findall(r'"(\w+)"|(\w+)', text_def.replace("PRIMARY KEY", ""))]
                continue
            cm = re.match(r"(\w+)\s+([A-Za-z]+(?:\s*\([^)]*\))?)(.*)$", text_def, re.S)
            if not cm:
                continue
            cols.append((cm.group(1), cm.group(2), "PRIMARY KEY" in upper, cm.group(3) or ""))
        if not cols:
            continue
        lines = [
            "class " + camel(table) + "(Base):",
            '    __tablename__ = "' + table + '"',
            '    __table_args__ = {"schema": "' + schema + '"}',
        ]
        for name, raw_type, inline_pk, remainder in cols:
            is_pk = inline_pk or name in pk_cols
            flag = ", primary_key=True" if is_pk else ""
            attr = RESERVED_ATTRS.get(name, name)
            col_arg = '"' + name + '", ' if attr != name else ""
            lines.append("    " + attr + " = mapped_column(" + col_arg + map_type(raw_type) + flag + default_expression(remainder) + ")")
        lines.append("")
        lines.append("")
        blocks.append("\n".join(lines))
    OUT.write_text("\n".join(header) + "\n".join(blocks), encoding="utf-8")
    print("tables", len(blocks), "->", OUT)


if __name__ == "__main__":
    main()
