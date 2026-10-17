"""L1 评测执行：确定性替身 + 桩化工具结果，逐条断言服务端链路。"""
import pytest

from eval.loader import load_cases
from eval.runner import checks_of, run_l1

CASES = load_cases(layer="L1")


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_eval_l1_case(case):
    result = run_l1(case)
    checks = checks_of(case, result)
    failed = {name: ok for name, ok in checks.items() if not ok}
    assert not failed, f"{case['id']} 断言失败 {failed} | 结果 {result}"
