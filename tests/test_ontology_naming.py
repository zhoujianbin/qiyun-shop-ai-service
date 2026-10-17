"""本体展示名：所有政策/故障/部件都要有中文名，且对照表与 yaml 保持完整。"""
import yaml
from sqlalchemy import text

from app.core.db import SessionLocal
from app.services.ontology import PART_LABELS, POLICY_LABELS

RULES = "knowledge_raw/13_结构化规则"


def _yaml(name: str) -> dict:
    with open(f"{RULES}/{name}", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def test_every_policy_rule_has_a_chinese_label():
    rules = (_yaml("policy_rules.yaml").get("rules") or {}).keys()
    missing = [rule_id for rule_id in rules if rule_id not in POLICY_LABELS]
    assert missing == [], f"以下政策缺中文名：{missing}"


def test_every_warranty_component_has_a_chinese_label():
    components = {item["component"] for item in (_yaml("product_warranty.yaml").get("rules") or [])}
    missing = sorted(components - set(PART_LABELS))
    assert missing == [], f"以下部件缺中文名：{missing}"


def test_no_policy_or_fault_entity_still_uses_a_code_as_name():
    with SessionLocal() as db:
        rows = db.execute(text(
            "select kind, code, name from ontology.entity"
            " where kind in ('policy', 'fault', 'part')"
            " and name !~ '[\\u4e00-\\u9fa5]' order by kind, code")).fetchall()
    assert rows == [], f"这些实体还在用编码当名称：{rows}"


def test_display_names_are_unique_per_kind():
    """同名不同码会让图谱难以分辨，这里只检查政策与部件。"""
    with SessionLocal() as db:
        duplicates = db.execute(text(
            "select kind, name, count(*) from ontology.entity"
            " where kind in ('policy', 'part') group by kind, name having count(*) > 1")).fetchall()
    assert duplicates == [], f"存在重名：{duplicates}"
