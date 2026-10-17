"""结构化规则：YAML 映射、六键条件校验、冲突检测、CRUD。

规则只做存储与冲突治理，不做运行时求值（属三期策略层）。
condition 键限定 6 个语义键；值可为标量或标量数组（数组 = 任一命中）。
"""
from __future__ import annotations

import pathlib

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError, NotFound, ValidationError
from app.models.generated import Rule, RuleConflict
from app.services import audit

CONDITION_KEYS = ("product_line", "issue_type", "order_state", "identity_level", "time_window", "component")
RULE_STATUSES = ("DRAFT", "ACTIVE", "ARCHIVED")
SOURCE_KINDS = ("policy", "warranty", "escalation", "manual")

# 只要用到"来源类型"的文件名（按 YAML 内容特征判定，不依赖文件名）
SUPPORTED_FILES = {
    "policy_rules.yaml": "policy",
    "product_warranty.yaml": "warranty",
    "escalation_matrix.yaml": "escalation",
}

# 政策类：语义（issue_type / 结论 / 冲突组）在这里定死，数值从 YAML 取
POLICY_SEMANTICS = {
    "RETURN-NO-REASON-7D": {
        "issue_type": "return_no_reason", "order_state": "COMPLETED",
        "decision": "ALLOW_RETURN", "conflict_group": "return_window", "basis": "delivery_date",
    },
    "QUALITY-ISSUE-RETURN-15D": {
        "issue_type": "quality_issue", "order_state": "COMPLETED",
        "decision": "ALLOW_RETURN", "conflict_group": "return_window", "basis": "delivery_date",
    },
    "QUALITY-ISSUE-EXCHANGE-30D": {
        "issue_type": "quality_issue", "order_state": "COMPLETED",
        "decision": "ALLOW_EXCHANGE", "conflict_group": "exchange_window", "basis": "delivery_date",
    },
    "REFUND-MERCHANT-PROCESS-3BD": {
        "issue_type": "refund", "decision": "REFUND_PROCESS_DEADLINE", "conflict_group": "refund_sla",
        "action_extra": {"refund_state": "ACCEPTED"},
    },
    "SHIPPING-FREE-99": {
        "issue_type": "shipping_fee", "decision": "FREE_SHIPPING", "conflict_group": "shipping_fee",
    },
    "LOGISTICS-STAGNANT-72H": {
        "issue_type": "logistics_stagnant", "order_state": "SHIPPED",
        "decision": "RAISE_STAGNANT_ALERT", "conflict_group": "logistics_alert", "basis": "last_tracking_update",
    },
    "ADDRESS-CHANGE-AFTER-SHIP": {
        "issue_type": "address_change", "order_state": "SHIPPED",
        "decision": "REQUEST_INTERCEPT_OR_REROUTE", "conflict_group": "address_change",
    },
    "INSTALL-RESCHEDULE-4H": {
        "issue_type": "install_reschedule", "decision": "ALLOW_RESCHEDULE", "conflict_group": "install_schedule",
    },
    "CLOUD-COOLING-OFF-7D": {
        "issue_type": "cloud_cooling_off", "order_state": "COMPLETED",
        "decision": "ALLOW_COOLING_OFF_REFUND", "conflict_group": "cloud_cooling_off", "basis": "activation_date",
    },
}

ESCALATION_PRIORITY = {"P0": 1000, "P1": 900, "P2": 600, "P3": 300}
TIME_KEYS = {"days_from_delivery": "max_days", "hours_without_update": "max_hours", "days": "max_days"}


# --------------------------------------------------------------------------
# 校验
# --------------------------------------------------------------------------
def validate_condition(condition: dict) -> dict:
    if not isinstance(condition, dict):
        raise ValidationError("condition 必须是对象")
    illegal = sorted(set(condition) - set(CONDITION_KEYS))
    if illegal:
        raise ValidationError(
            "condition 含非法键：" + "、".join(illegal) + "；允许 " + "、".join(CONDITION_KEYS)
        )
    return condition


# --------------------------------------------------------------------------
# YAML 映射
# --------------------------------------------------------------------------
def _map_policy(rule_id: str, body: dict) -> dict:
    meta = POLICY_SEMANTICS.get(rule_id)
    if meta is None:
        raise ValidationError(f"未知的政策规则：{rule_id}")
    condition = {"issue_type": meta["issue_type"]}
    if meta.get("order_state"):
        condition["order_state"] = meta["order_state"]
    action = {"decision": meta["decision"], **meta.get("action_extra", {})}
    for key, value in body.items():
        if key in TIME_KEYS and meta.get("basis"):
            condition["time_window"] = {"basis": meta["basis"], TIME_KEYS[key]: value}
        elif key in ("conditions", "requires"):
            action["requires"] = value
        elif key == "action":
            action.setdefault("action", value)
        else:
            action[key] = value
    return {
        "rule_id": rule_id,
        "source_kind": "policy",
        "condition": condition,
        "action": action,
        "forbid": [],
        "priority": 100,
        "conflict_group": meta["conflict_group"],
    }


def _map_warranty(entry: dict) -> dict:
    return {
        "rule_id": str(entry["rule_id"]),
        "source_kind": "warranty",
        "condition": {
            "product_line": str(entry["product_id"]),
            "issue_type": "warranty_claim",
            "component": str(entry["component"]),
        },
        "action": {"decision": "COVER_UNDER_WARRANTY", "months": int(entry["months"])},
        "forbid": [],
        "priority": 200,
        "conflict_group": "warranty_coverage",
    }


def _map_escalation(rule_id: str, body: dict) -> dict:
    priority = ESCALATION_PRIORITY.get(str(body.get("priority", "P3")).upper(), 300)
    return {
        "rule_id": rule_id,
        "source_kind": "escalation",
        "condition": {"issue_type": list(body.get("triggers", []))},
        "action": {
            "decision": "ESCALATE",
            "target": body.get("target"),
            "response_minutes": body.get("response_minutes"),
        },
        "forbid": list(body.get("prohibit", [])),
        "priority": priority,
        "conflict_group": "escalation",
    }


def map_yaml(file_name: str, payload: bytes) -> list[dict]:
    """把一个规则 YAML 映射成规则行；不在纳管范围的形态直接拒绝。"""
    source_kind = SUPPORTED_FILES.get(pathlib.Path(file_name).name)
    if source_kind is None:
        raise AppError(
            "RULE_FORM_NOT_MANAGED",
            f"{file_name}：该形态不纳管。只接受 {', '.join(sorted(SUPPORTED_FILES))}",
            400,
        )
    try:
        data = yaml.safe_load(payload.decode("utf-8")) or {}
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise ValidationError(f"{file_name}：YAML 解析失败：{exc}") from exc
    if not isinstance(data, dict):
        raise ValidationError(f"{file_name}：YAML 顶层必须是对象")

    rules: list[dict] = []
    if source_kind == "policy":
        for rule_id, body in (data.get("rules") or {}).items():
            rules.append(_map_policy(str(rule_id), body or {}))
    elif source_kind == "warranty":
        for entry in data.get("rules") or []:
            if isinstance(entry, dict) and entry.get("rule_id"):
                rules.append(_map_warranty(entry))
    else:
        for rule_id, body in (data.get("rules") or {}).items():
            rules.append(_map_escalation(str(rule_id), body or {}))

    for rule in rules:
        validate_condition(rule["condition"])
    return rules


# --------------------------------------------------------------------------
# 冲突检测
# --------------------------------------------------------------------------
def _as_list(value) -> list:
    return value if isinstance(value, list) else [value]


def _conditions_intersect(left: dict, right: dict) -> bool:
    for key in CONDITION_KEYS:
        if key not in left or key not in right:
            continue
        if key == "time_window":
            if not _windows_overlap(left[key], right[key]):
                return False
            continue
        if not set(_as_list(left[key])) & set(_as_list(right[key])):
            return False
    return True


def _windows_overlap(left: dict, right: dict) -> bool:
    if (left or {}).get("basis") != (right or {}).get("basis"):
        return False  # 起算点不同，视为不同时间轴
    for unit in ("max_days", "max_hours"):
        if unit in left and unit in right:
            # 同为"上限"语义：较小者被较大者包含
            return True
    return True


def _is_negative(decision: str) -> bool:
    return decision.startswith(("DENY_", "NOT_", "CHARGE_", "REJECT_", "FORBID_"))


def _decisions_conflict(left: dict, right: dict) -> tuple[bool, str]:
    a = str((left or {}).get("decision", ""))
    b = str((right or {}).get("decision", ""))
    if not a or not b:
        return False, ""
    if a == b:
        return (left or {}) != (right or {}), "SAME_DECISION_DIFFERENT_PARAMS"
    if _is_negative(a) != _is_negative(b):
        return True, "MUTUALLY_EXCLUSIVE"
    return False, ""


def detect_conflicts(rules: list[Rule]) -> list[dict]:
    """同冲突组内两两比较：条件相交 + 结论冲突 -> 阻断级；同结论不同参数 -> 提醒级。"""
    found: list[dict] = []
    ordered = sorted(rules, key=lambda rule: rule.id)
    for index, left in enumerate(ordered):
        for right in ordered[index + 1:]:
            if (left.conflict_group or "") != (right.conflict_group or ""):
                continue
            if not _conditions_intersect(left.condition or {}, right.condition or {}):
                continue
            conflict, kind = _decisions_conflict(left.action or {}, right.action or {})
            if not conflict:
                continue
            severity = "BLOCK" if kind == "MUTUALLY_EXCLUSIVE" else "WARN"
            found.append({
                "rule_a_id": left.id,
                "rule_b_id": right.id,
                "conflict_type": kind,
                "severity": severity,
                "detail": {"group": left.conflict_group, "a": left.rule_id, "b": right.rule_id},
            })
    return found


def sync_conflicts(db: Session) -> list[RuleConflict]:
    """重算冲突并落库：已消失的 OPEN 记录标记 IGNORED。"""
    from app.services.common import now
    moment = now()
    rules = list(db.execute(
        select(Rule).where(
            Rule.status == "ACTIVE",
            (Rule.effective_from.is_(None)) | (Rule.effective_from <= moment),
            (Rule.effective_until.is_(None)) | (Rule.effective_until > moment),
        )
    ).scalars().all())
    detected = detect_conflicts(rules)
    existing = {(row.rule_a_id, row.rule_b_id, row.conflict_type): row
                for row in db.execute(select(RuleConflict)).scalars().all()}
    seen = set()
    for item in detected:
        key = (item["rule_a_id"], item["rule_b_id"], item["conflict_type"])
        seen.add(key)
        row = existing.get(key)
        if row is None:
            db.add(RuleConflict(tenant_id=settings.tenant_id, **item))
        else:
            row.severity = item["severity"]
            if row.status == "IGNORED":
                row.status = "OPEN"
    for key, row in existing.items():
        if key not in seen and row.status == "OPEN":
            row.status = "IGNORED"
    db.flush()
    return list(db.execute(select(RuleConflict).where(RuleConflict.status == "OPEN")).scalars().all())


def open_blocking_conflicts(db: Session) -> list[RuleConflict]:
    return list(db.execute(
        select(RuleConflict).where(RuleConflict.status == "OPEN", RuleConflict.severity == "BLOCK")
    ).scalars().all())


def resolve_conflict(db: Session, actor: dict, conflict_id: int) -> dict:
    row = db.get(RuleConflict, conflict_id)
    if row is None or row.tenant_id != settings.tenant_id:
        raise NotFound("冲突记录不存在")
    row.status = "RESOLVED"
    row.resolved_by = actor.get("id")
    from app.services.common import now
    row.resolved_at = now()
    audit.record(db, actor, "knowledge.rule_conflict.resolve", "knowledge.rule_conflict", row.id,
                 before={"status": "OPEN"}, after={"status": "RESOLVED"})
    db.flush()
    return conflict_view(row)


# --------------------------------------------------------------------------
# CRUD 与视图
# --------------------------------------------------------------------------
def rule_view(rule: Rule) -> dict:
    return {
        "id": rule.id,
        "rule_id": rule.rule_id,
        "source_kind": rule.source_kind,
        "condition": rule.condition or {},
        "action": rule.action or {},
        "forbid": rule.forbid or [],
        "priority": rule.priority,
        "status": rule.status,
        "conflict_group": rule.conflict_group,
        "source_file": rule.source_file,
        "source_line": rule.source_line,
        "effective_from": rule.effective_from.isoformat() if rule.effective_from else None,
        "effective_until": rule.effective_until.isoformat() if rule.effective_until else None,
    }


def conflict_view(row: RuleConflict) -> dict:
    return {
        "id": row.id,
        "rule_a_id": row.rule_a_id,
        "rule_b_id": row.rule_b_id,
        "conflict_type": row.conflict_type,
        "severity": row.severity,
        "status": row.status,
        "detail": row.detail or {},
        "resolved_by": row.resolved_by,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
    }


def import_yaml(db: Session, actor: dict, files: list[tuple[str, bytes]]) -> dict:
    """规则 YAML 导入：整批校验通过才落库（避免半批脏数据）。"""
    if not files:
        raise ValidationError("没有上传任何规则文件")
    mapped: list[dict] = []
    for file_name, payload in files:
        for rule in map_yaml(file_name, payload):
            rule["source_file"] = pathlib.Path(file_name).name
            mapped.append(rule)

    imported = updated = 0
    for item in mapped:
        existing = db.execute(
            select(Rule).where(Rule.tenant_id == settings.tenant_id, Rule.rule_id == item["rule_id"])
        ).scalar_one_or_none()
        if existing is None:
            db.add(Rule(
                tenant_id=settings.tenant_id,
                rule_id=item["rule_id"],
                source_kind=item["source_kind"],
                condition=item["condition"],
                action=item["action"],
                forbid=item["forbid"],
                priority=item["priority"],
                status="ACTIVE",
                conflict_group=item["conflict_group"],
                source_file=item["source_file"],
            ))
            imported += 1
        else:
            existing.condition = item["condition"]
            existing.action = item["action"]
            existing.forbid = item["forbid"]
            existing.priority = item["priority"]
            existing.conflict_group = item["conflict_group"]
            existing.source_kind = item["source_kind"]
            existing.source_file = item["source_file"]
            existing.status = "ACTIVE"
            updated += 1
    db.flush()
    conflicts = sync_conflicts(db)
    audit.record(db, actor, "knowledge.rule.import", "knowledge.rule", None,
                 after={"imported": imported, "updated": updated, "files": len(files)})
    by_kind: dict[str, int] = {}
    for item in mapped:
        by_kind[item["source_kind"]] = by_kind.get(item["source_kind"], 0) + 1
    return {
        "imported": imported,
        "updated": updated,
        "total": len(mapped),
        "by_source_kind": by_kind,
        "open_conflicts": len(conflicts),
    }


def list_rules(db: Session, *, status: str | None = None, source_kind: str | None = None) -> list[dict]:
    statement = select(Rule).where(Rule.tenant_id == settings.tenant_id)
    if status:
        statement = statement.where(Rule.status == status)
    if source_kind:
        statement = statement.where(Rule.source_kind == source_kind)
    return [rule_view(rule) for rule in db.execute(statement.order_by(Rule.id)).scalars().all()]


def get_rule(db: Session, rule_pk: int) -> dict:
    rule = db.get(Rule, rule_pk)
    if rule is None or rule.tenant_id != settings.tenant_id:
        raise NotFound("规则不存在")
    return rule_view(rule)


def create_rule(db: Session, actor: dict, payload: dict) -> dict:
    validate_condition(payload.get("condition") or {})
    rule_id = str(payload.get("rule_id") or "").strip()
    if not rule_id:
        raise ValidationError("rule_id 必填")
    if db.execute(select(Rule).where(Rule.tenant_id == settings.tenant_id, Rule.rule_id == rule_id)).scalar_one_or_none():
        raise ValidationError(f"rule_id 已存在：{rule_id}")
    source_kind = payload.get("source_kind") or "manual"
    if source_kind not in SOURCE_KINDS:
        raise ValidationError(f"source_kind 非法：{source_kind}")
    rule = Rule(
        tenant_id=settings.tenant_id,
        rule_id=rule_id,
        source_kind=source_kind,
        condition=payload["condition"],
        action=payload.get("action") or {},
        forbid=payload.get("forbid") or [],
        priority=int(payload.get("priority") or 100),
        status=str(payload.get("status") or "DRAFT").upper(),
        conflict_group=payload.get("conflict_group"),
    )
    db.add(rule)
    db.flush()
    sync_conflicts(db)
    audit.record(db, actor, "knowledge.rule.create", "knowledge.rule", rule.id, after=rule_view(rule))
    return rule_view(rule)


def update_rule(db: Session, actor: dict, rule_pk: int, payload: dict) -> dict:
    rule = db.get(Rule, rule_pk)
    if rule is None or rule.tenant_id != settings.tenant_id:
        raise NotFound("规则不存在")
    before = rule_view(rule)
    if "condition" in payload and payload["condition"] is not None:
        rule.condition = validate_condition(payload["condition"])
    for field in ("action", "forbid", "priority", "status", "conflict_group", "effective_from", "effective_until"):
        if field in payload and payload[field] is not None:
            value = payload[field]
            if field == "status":
                value = str(value).upper()
                if value not in RULE_STATUSES:
                    raise ValidationError(f"status 非法：{value}")
            setattr(rule, field, value)
    db.flush()
    sync_conflicts(db)
    audit.record(db, actor, "knowledge.rule.update", "knowledge.rule", rule.id, before=before, after=rule_view(rule))
    return rule_view(rule)
