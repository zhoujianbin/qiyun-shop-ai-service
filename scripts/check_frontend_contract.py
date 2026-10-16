#!/usr/bin/env python3
"""校验前端接口调用与后端运行时 OpenAPI 契约一致（路径 + 方法）。

前端接口统一在 web/src/api/endpoints/*.ts 中集中声明，本脚本扫描这些 api.get/post/... 调用，
与后端运行时导出的 OpenAPI paths 做匹配，确保前端不会调用不存在的接口或方法。

用法：python scripts/check_frontend_contract.py
退出码：0 全部一致；1 存在不一致。
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

METHODS = ("get", "post", "put", "patch", "delete")
CALL = re.compile(r"api\.(get|post|put|patch|delete)<[^>]*>\(\s*[\'\"\+\s]*([\'\"\x60])(/[^\'\"\x60]*)[\'\"\x60]")
CALL2 = re.compile(r"api\.(get|post|put|patch|delete)\(\s*[\'\"\x60](/[^\'\"\x60]*)[\'\"\x60]")


def normalize(raw: str) -> str:
    path = raw.split("?")[0]
    path = re.sub(r"\$\{[^}]+\}", "{param}", path)
    path = re.sub(r"\{[^}]+\}", "{param}", path)
    return path.rstrip("/") or "/"


def full(raw: str) -> str:
    path = normalize(raw)
    return path if path.startswith("/api/v1") else "/api/v1" + path


def main() -> int:
    spec = app.openapi()
    contract = {path: {m.upper() for m in item if m in METHODS} for path, item in spec["paths"].items()}
    invocations = []
    for src in sorted((ROOT / "web" / "src").rglob("*.ts")):
        if "generated" in src.parts:
            continue
        text = src.read_text(encoding="utf-8", errors="ignore")
        for regex in (CALL, CALL2):
            for match in regex.finditer(text):
                method = match.group(1).upper()
                raw = match.group(3) if regex is CALL else match.group(2)
                invocations.append((src.relative_to(ROOT).as_posix(), method, raw))

    problems = []
    checked = 0
    for source, method, raw in invocations:
        if raw.endswith("/"):
            prefix = full(raw)
            candidates = {p for p in contract if p.startswith(prefix) and p != prefix.rstrip("/")}
            if not candidates:
                problems.append(f"{source}: {method} {raw}<动态> -> 运行时契约不存在此前缀")
                continue
            checked += 1
            if not any(method in contract[c] for c in candidates):
                problems.append(f"{source}: {method} {raw}<动态> -> 前缀路径不支持 {method}")
            continue
        target = full(raw)
        candidates = {p for p in contract if normalize(p) == target}
        if not candidates:
            problems.append(f"{source}: {method} {raw} -> 运行时契约不存在该路径")
            continue
        checked += 1
        if not any(method in contract[c] for c in candidates):
            problems.append(f"{source}: {method} {raw} -> 该路径不支持 {method}")

    print(f"contract_paths={len(spec['paths'])} frontend_calls={len(invocations)} checked={checked} problems={len(problems)}")
    for problem in problems:
        print("  PROBLEM", problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
