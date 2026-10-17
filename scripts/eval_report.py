#!/usr/bin/env python3
"""四期评测报告：L1 确定性链路 + L2 真实模型观察，分表呈现，不产总分。

用法：
  python scripts/eval_report.py            # 跑 L1 并读取已有 L2 结果
  python scripts/eval_report.py --json     # 只打印 JSON
输出：var/eval_report.json + var/eval_report.md（var/ 已被 gitignore）
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.loader import load_cases  # noqa: E402
from eval.runner import checks_of, run_l1  # noqa: E402

VAR = ROOT / "var"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    l1_results = []
    for case in load_cases(layer="L1"):
        result = run_l1(case)
        checks = checks_of(case, result)
        l1_results.append({
            "id": case["id"], "category": case["category"], "question": case["question"],
            "checks": checks, "passed": bool(checks) and all(checks.values()),
            "decision": result.get("decision"), "tools": result.get("tool_calls_ok"),
            "citations": result.get("citations"), "entities": result.get("entities"),
            "error": result.get("error"),
        })
    l2_path = VAR / "eval_l2.json"
    l2_results = json.loads(l2_path.read_text(encoding="utf-8")) if l2_path.exists() else {}

    payload = {
        "L1": {
            "total": len(l1_results),
            "passed": sum(1 for item in l1_results if item["passed"]),
            "by_category": {},
            "failures": [item for item in l1_results if not item["passed"]],
            "cases": l1_results,
        },
        "L2": {"total_cases": len(load_cases(layer="L2")),
               "observed": len(l2_results), "results": l2_results},
        "note": "L1 阻断门禁、L2 只记录；两表分开，不计算总分",
    }
    for item in l1_results:
        bucket = payload["L1"]["by_category"].setdefault(
            item["category"], {"total": 0, "passed": 0})
        bucket["total"] += 1
        bucket["passed"] += 1 if item["passed"] else 0

    VAR.mkdir(exist_ok=True)
    (VAR / "eval_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    lines = ["# 四期评测报告", "",
             "> L1 = 确定性链路门禁；L2 = 真实模型观察（只记录）。两表分开，不计算总分。", "",
             "## L1", "", f"通过 {payload['L1']['passed']}/{payload['L1']['total']}", "",
             "| 类别 | 通过 | 总数 |", "|---|---|---|"]
    for category, bucket in sorted(payload["L1"]["by_category"].items()):
        lines.append(f"| {category} | {bucket['passed']} | {bucket['total']} |")
    if payload["L1"]["failures"]:
        lines += ["", "### 失败用例", ""]
        for item in payload["L1"]["failures"]:
            lines.append(f"- {item['id']} {item['question']} → {item['checks']} {item['error'] or ''}")
    lines += ["", "## L2", "",
              f"已观察 {payload['L2']['observed']}/{payload['L2']['total_cases']} 条", ""]
    if l2_results:
        lines += ["| 用例 | finish_reason | 字符数 |", "|---|---|---|"]
        for key, value in sorted(l2_results.items()):
            lines.append(f"| {key} | {value.get('finish_reason')} | {value.get('chars')} |")
        lines.append("")
    (VAR / "eval_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps({k: payload[k] for k in ("L1", "L2", "note")}, ensure_ascii=False,
                         indent=1)[:4000])
    else:
        print(f"L1 {payload['L1']['passed']}/{payload['L1']['total']} 通过")
        print(f"L2 已观察 {payload['L2']['observed']}/{payload['L2']['total_cases']}")
        print("报告：var/eval_report.json, var/eval_report.md")
    return 0 if payload["L1"]["passed"] == payload["L1"]["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
