"""四期补丁：实体归一模糊兜底 + 产品名宽松命中（仅排序）。"""
from app.core.db import SessionLocal
from app.services import ontology


def _norm(question: str) -> dict:
    with SessionLocal() as db:
        return ontology.normalize_question(db, question)


def test_exact_alias_still_wins():
    result = _norm("指纹识别差怎么办")
    assert result["method"] == "exact"
    assert [item["code"] for item in result["entities"]] == ["SYM-QL-L3P-02"]


def test_fuzzy_matches_typo_variant():
    result = _norm("指纹识别不好怎么办")
    assert result["method"] == "fuzzy"
    assert [item["code"] for item in result["entities"]] == ["SYM-QL-L3P-02"]
    assert result["entities"][0]["method"] == "fuzzy"


def test_unrelated_question_does_not_fuzzy_match():
    result = _norm("怎么退款")
    assert result["method"] is None
    assert result["entities"] == []


def test_fuzzy_requires_shared_grams_and_does_not_guess():
    """只共享一个二元组时不许命中（避免巧合匹配）。"""
    result = _norm("门")
    assert result["entities"] == []


def test_product_name_loose_match_only_boosts_and_never_filters():
    result = _norm("看看我订单里门锁的那个的状态")
    assert result["entities"] == []
    assert result["product_scope"] is None          # 不过滤
    assert [item["code"] for item in result["boost_entities"]] == ["QL-L3P"]


def test_boost_wins_over_part_derived_scope():
    """用户明说"门锁电池"时，范围应取门锁而不是电池唯一所属的扫地机。"""
    result = _norm("门锁电池能用多久")
    assert result["product_scope"] == "QL-L3P"
