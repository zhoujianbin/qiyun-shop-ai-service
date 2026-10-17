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

def test_vector_booster_only_reorders_never_filters(monkeypatch):
    """向量兜底只进 boost：不改 entities、不改 product_scope。"""
    from app.integrations import embedding
    from app.services import ontology

    with SessionLocal() as db:
        items = ontology._entity_vectors(db)
        assert items, "实体向量缓存应已构建"
        target, vector = items[0]
        # 让 query 向量等于目标实体向量，另造一个明显更远的第二候选
        monkeypatch.setattr(embedding, "encode_query", lambda text: list(vector))
        hit = ontology._vector_entity(db, "随便问点什么")
        assert hit is not None and hit.code == target.code

        result = ontology.normalize_question(db, "随便问点什么")
        assert result["method"] is None
        assert result["entities"] == []
        assert result["product_scope"] is None
        assert target.code in [item["code"] for item in result["boost_entities"]]


def test_vector_booster_rejects_small_margin(monkeypatch):
    from app.integrations import embedding
    from app.services import ontology

    with SessionLocal() as db:
        items = ontology._entity_vectors(db)
        first, second = items[0][1], items[1][1]
        # 构造与两个实体等距的向量（两者相似度相同 -> 间距为 0）
        mixed = [a + b for a, b in zip(first, second)]
        norm = sum(x * x for x in mixed) ** 0.5 or 1.0
        monkeypatch.setattr(embedding, "encode_query", lambda _text: [x / norm for x in mixed])
        # 并列候选必须放弃（避免误命中）
        assert ontology._vector_entity(db, "随便问点什么") is None


def test_fuzzy_and_vector_do_not_derive_product_scope():
    """只由模糊命中时不得推导 product_scope（避免把策略/故障编码当产品范围）。"""
    with SessionLocal() as db:
        result = ontology.normalize_question(db, "打不开门了怎么办")
        assert result["product_scope"] is None
