"""模型与 DDL 一致性测试：避免生成器遗漏列（曾出现 CHECKSUM_ 被误判为 CHECK 约束）。"""
import pathlib
import re

from app.models import Base

ROOT = pathlib.Path(__file__).resolve().parents[1]
DDL = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")


def _split_top(body: str):
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


def ddl_columns() -> dict[tuple[str, str], set[str]]:
    result = {}
    for m in re.finditer(r"CREATE TABLE\s+(\w+)\.(\w+)\s*\(", DDL):
        schema, table = m.group(1), m.group(2)
        if schema not in ("shared", "commerce"):
            continue
        start = m.end()
        depth, end = 1, start
        while depth > 0:
            ch = DDL[end]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            end += 1
        cols = set()
        for part in _split_top(DDL[start:end - 1]):
            text = part.strip()
            if not text:
                continue
            upper = text.upper()
            if re.match(r"^(CONSTRAINT|FOREIGN\s+KEY|UNIQUE|CHECK|PRIMARY\s+KEY)\b", upper):
                continue
            cm = re.match(r"(\w+)\s+[A-Za-z]+", text)
            if cm:
                cols.add(cm.group(1))
        result[(schema, table)] = cols
    return result


def model_columns() -> dict[tuple[str, str], set[str]]:
    return {(t.schema, t.name): {c.name for c in t.columns} for t in Base.metadata.tables.values()}


def test_every_ddl_column_is_mapped():
    ddl = ddl_columns()
    model = model_columns()
    missing_tables, missing_columns = [], []
    for key, cols in ddl.items():
        if key not in model:
            missing_tables.append(key)
            continue
        for column in sorted(cols - model[key]):
            missing_columns.append(f"{key[0]}.{key[1]}.{column}")
    assert not missing_tables, f"缺少模型：{missing_tables}"
    assert not missing_columns, f"模型缺少列：{missing_columns}"


def test_no_extra_mapped_columns():
    ddl = ddl_columns()
    model = model_columns()
    extra = []
    for key, cols in model.items():
        for column in sorted(cols - ddl.get(key, set())):
            extra.append(f"{key[0]}.{key[1]}.{column}")
    assert not extra, f"模型存在 DDL 中不存在的列：{extra}"


def test_primary_keys_match():
    ddl_pk = {}
    for m in re.finditer(r"CREATE TABLE\s+(\w+)\.(\w+)\s*\(", DDL):
        schema, table = m.group(1), m.group(2)
        if schema not in ("shared", "commerce"):
            continue
        start = m.end()
        depth, end = 1, start
        while depth > 0:
            ch = DDL[end]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            end += 1
        pk = set()
        for part in _split_top(DDL[start:end - 1]):
            text = part.strip()
            if text.upper().startswith("PRIMARY KEY"):
                pk |= set(re.findall(r"(\w+)", text.replace("PRIMARY KEY", "")))
            elif "PRIMARY KEY" in text.upper() and re.match(r"^\w+\s", text):
                pk.add(text.split()[0])
        ddl_pk[(schema, table)] = pk
    for key, expected in ddl_pk.items():
        table = Base.metadata.tables.get(f"{key[0]}.{key[1]}")
        if table is None:
            continue
        actual = {c.name for c in table.primary_key.columns}
        assert actual == expected, f"{key} 主键不一致：模型 {actual} vs DDL {expected}"
