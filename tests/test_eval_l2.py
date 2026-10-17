"""L2 真实模型观察层：只记录不阻断（pytest.ini 默认排除 eval_live）。

运行方式：python -m pytest -m eval_live -q
"""
import json
import pathlib

import pytest

from eval.loader import load_cases

L2_CASES = load_cases(layer="L2")
REPORT = pathlib.Path(__file__).resolve().parents[1] / "var" / "eval_l2.json"


@pytest.mark.eval_live
@pytest.mark.parametrize("case", L2_CASES, ids=[case["id"] for case in L2_CASES])
def test_eval_l2_observe(case):
    """不做硬断言，只验证用例可执行并记录（真实模型调用）。"""
    from app.integrations import llm

    response = llm.complete([{"role": "user", "content": case["question"]}])
    REPORT.parent.mkdir(exist_ok=True)
    existing = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
    existing[case["id"]] = {"question": case["question"],
                            "finish_reason": response.get("finish_reason"),
                            "chars": len(response.get("text") or "")}
    REPORT.write_text(json.dumps(existing, ensure_ascii=False, indent=1), encoding="utf-8")
    assert response.get("text") is not None
