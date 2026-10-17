"""评测用例契约：字段齐、id 唯一、枚举合法、每条 L1 至少一种断言。"""
from eval.loader import CATEGORIES, LAYERS, load_cases, problems_of


def test_every_case_has_required_fields_and_valid_enums():
    cases = load_cases()
    assert cases, "没有加载到任何用例"
    problems = [(case["id"], problem) for case in cases for problem in problems_of(case)]
    assert problems == []


def test_case_ids_are_unique():
    ids = [case["id"] for case in load_cases()]
    assert len(ids) == len(set(ids))


def test_eval_l1_has_at_least_60_cases_and_covers_all_categories():
    l1 = load_cases(layer="L1")
    assert len(l1) >= 60, f"L1 用例不足：{len(l1)}"
    assert {case["category"] for case in l1} == CATEGORIES


def test_layer_values_are_known():
    assert {case["layer"] for case in load_cases()} <= LAYERS


def test_safety_cases_come_from_red_team_sources():
    safety = [case for case in load_cases() if case["category"] == "safety"]
    assert safety, "缺少安全用例"
    assert any("SCN-017" in str(case.get("notes")) for case in safety)
    assert any("SCN-018" in str(case.get("notes")) for case in safety)
