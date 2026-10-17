"""评测用例加载与校验：目录即真源，不建表。"""
from __future__ import annotations

import pathlib

import yaml

CASES_DIR = pathlib.Path(__file__).resolve().parents[1] / "eval" / "cases"
CATEGORIES = {"knowledge", "tool_read", "tool_write", "identity", "refuse", "safety"}
LAYERS = {"L1", "L2"}
REQUIRED = ("id", "category", "layer", "question")


def load_cases(*, layer: str | None = None) -> list[dict]:
    cases: list[dict] = []
    for path in sorted(CASES_DIR.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for item in payload.get("cases") or []:
            case = dict(item)
            case["_file"] = path.name
            if layer is None or case.get("layer") == layer:
                cases.append(case)
    return cases


def problems_of(case: dict) -> list[str]:
    """返回该用例的结构问题；空列表表示合法。"""
    problems = []
    for key in REQUIRED:
        if not case.get(key):
            problems.append(f"缺少字段 {key}")
    if case.get("category") not in CATEGORIES:
        problems.append(f"category 非法：{case.get('category')}")
    if case.get("layer") not in LAYERS:
        problems.append(f"layer 非法：{case.get('layer')}")
    for key in ("must_call_tool", "must_not_call_tool"):
        if key in case and not isinstance(case[key], list):
            problems.append(f"{key} 必须是列表")
    if case.get("layer") == "L1" and not any(
            key in case for key in ("must_call_tool", "must_not_call_tool", "must_cite",
                                    "must_refuse", "must_handoff", "must_confirm",
                                    "must_request_identity", "forbidden_patterns",
                                    "expected_entities")):
        problems.append("L1 用例至少要有一种断言")
    return problems
