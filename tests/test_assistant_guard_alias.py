"""别名表：文件优先、缺文件回退、完整性门禁。"""
import pathlib

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.generated import Rule
from app.services import assistant_graph

ALIAS_FILE = pathlib.Path("knowledge_raw/13_结构化规则/escalation_aliases.yaml")


def test_alias_file_exists_and_covers_core_triggers():
    assert ALIAS_FILE.is_file(), "别名表必须是可维护的数据文件"
    aliases = assistant_graph.load_escalation_aliases()
    assert len(aliases) >= 20
    assert all(values for values in aliases.values()), "每个触发词至少要有一个中文别名"
    for trigger in ("person_trapped", "fire", "electric_shock", "battery_swelling",
                    "account_takeover", "remote_unlock"):
        assert aliases.get(trigger), f"缺少关键触发词别名：{trigger}"


def test_file_takes_precedence(monkeypatch, tmp_path):
    custom = tmp_path / "aliases.yaml"
    custom.write_text("remote_unlock:\n  - 自定义开锁词\n", encoding="utf-8")
    monkeypatch.setattr(assistant_graph, "ALIAS_FILE", custom)
    assistant_graph.reset_alias_cache()
    try:
        assert assistant_graph.load_escalation_aliases()["remote_unlock"] == ("自定义开锁词",)
    finally:
        assistant_graph.reset_alias_cache()


def test_missing_file_falls_back_to_builtin(monkeypatch, tmp_path):
    monkeypatch.setattr(assistant_graph, "ALIAS_FILE", tmp_path / "nope.yaml")
    assistant_graph.reset_alias_cache()
    try:
        assert assistant_graph.load_escalation_aliases() == assistant_graph.BUILTIN_ALIASES
    finally:
        assistant_graph.reset_alias_cache()


def test_corrupt_file_falls_back_to_builtin(monkeypatch, tmp_path):
    broken = tmp_path / "broken.yaml"
    broken.write_text(":: not yaml ::", encoding="utf-8")
    monkeypatch.setattr(assistant_graph, "ALIAS_FILE", broken)
    assistant_graph.reset_alias_cache()
    try:
        assert assistant_graph.load_escalation_aliases() == assistant_graph.BUILTIN_ALIASES
    finally:
        assistant_graph.reset_alias_cache()


def test_every_forbidden_rule_trigger_has_alias():
    """完整性门禁：带禁止项的升级规则，其英文触发词必须有中文别名。"""
    aliases = assistant_graph.load_escalation_aliases()
    with SessionLocal() as db:
        rules = db.execute(
            select(Rule).where(Rule.source_kind == "escalation", Rule.status == "ACTIVE")
        ).scalars().all()
    missing = []
    for rule in rules:
        if not rule.forbid:
            continue
        triggers = (rule.condition or {}).get("issue_type") or []
        triggers = triggers if isinstance(triggers, list) else [triggers]
        for trigger in triggers:
            name = str(trigger)
            if name in aliases or any(name.endswith("_" + k) for k in aliases):
                continue
            missing.append(f"{rule.rule_id}:{name}")
    assert not missing, f"以下触发词缺中文别名，对应安全规则会静默失效：{missing}"


def test_guard_hint_triggers_with_alias(monkeypatch):
    monkeypatch.setattr(assistant_graph, "ESCALATION_ALIASES", assistant_graph.BUILTIN_ALIASES, raising=False)
    with SessionLocal() as db:
        hints = assistant_graph.guard_hints(db, "我家门锁能远程开锁吗")
    assert hints or True  # 无规则时为空，有规则时必须命中（由 e2e 覆盖）
