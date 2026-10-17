"""四期本体抽取（候选生成）：从产品故障诊断文档抽取故障现象、部件归属与处置动作。

定位：候选生成器，产出全部为 DRAFT，必须经审核（ontology.review）才对检索生效。
能被抽取的都有出处（source_doc + 行号）；抽不出来的一律跳过，不猜。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.generated import Alias, Entity, Relation
from app.services import audit

ROOT = Path(__file__).resolve().parents[2]
PRODUCT_DOCS = ROOT / "knowledge_raw" / "01_产品知识"


@dataclass(frozen=True)
class PartRule:
    part_code: str
    keywords: tuple[str, ...]


# 顺序即优先级：先具体后笼统
PART_RULES: tuple[PartRule, ...] = (
    PartRule("lock_cylinder", ("锁芯", "机械钥匙", "钥匙")),
    PartRule("battery", ("电池", "电量", "续航", "鼓包", "充电", "发热")),
    PartRule("lamp_and_driver", ("灯体", "驱动", "频闪", "亮度", "灯珠")),
    PartRule("robot_and_dock", ("基站", "回充", "尘盒", "主刷", "拖布", "清洁效果")),
    PartRule("lock_body_and_electronics", ("指纹", "密码", "门卡", "NFC", "面板", "开锁", "主板", "电机", "识别")),
    PartRule("main_unit", ("配网", "联网", "WiFi", "wifi", "离线", "建图", "主机", "整机", "信号", "录像", "访问")),
)

# 升级触发词（冒烟/触电/鼓包…）不再映射到具体部件。
# 理由：它们是跨产品的安全事件，绑到某个部件后，图遍历会把"相机冒烟"推到"门锁锁体保修"，
# 这类串台在四期审核里已经被判 4 条 warn。安全事件只保留 ESCALATES_TO。

# 处置动作（handling=true，不对应工具；与 tool 动作区分）
HANDLING_ACTIONS: dict[str, str] = {
    "action.clean_and_retry": "清洁/复位后重试",
    "action.remote_troubleshoot": "远程指导下排查",
    "action.collect_evidence": "收集订单号与现场凭证",
    "action.create_ticket": "创建技术工单",
    "action.on_site_visit": "安排上门检测",
    "action.turn_human": "转人工处理",
}

REMEDY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("action.on_site_visit", ("上门", "工程师", "现场")),
    ("action.create_ticket", ("工单", "报修", "技术")),
    ("action.collect_evidence", ("照片", "凭证", "录屏", "序列号")),
    ("action.clean_and_retry", ("清洁", "复位", "重试", "重启", "重新录入")),
    ("action.turn_human", ("转人工", "人工", "客服")),
)

HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")

# 06_保修维修与备件 没有"故障现象"，承载的是政策与流程条文。
# 这里只落**文档点名过**的政策，以及条文里明确写出的动作；不推断、不扩写。
SERVICE_DOCS = ROOT / "knowledge_raw" / "06_保修维修与备件"


@dataclass(frozen=True)
class ServiceRule:
    code: str
    name: str
    doc: str                      # 相对 knowledge_raw 的路径
    actions: tuple[str, ...]
    aliases: tuple[str, ...] = ()  # 用户口语里的短说法，太长没人这么问


SERVICE_RULES: tuple[ServiceRule, ...] = (
    ServiceRule("REPAIR-PAID-QUOTE", "付费维修报价与确认",
                "06_保修维修与备件/付费维修与报价确认.md", ("action.quote_and_confirm",),
                ("付费维修", "维修报价")),
    ServiceRule("WARRANTY-EXCLUSIONS", "保修范围与排除项",
                "06_保修维修与备件/保修范围与排除项.md", (),
                ("保修范围", "保修排除项")),
    ServiceRule("SPARE-PART-WAITING", "备件等待与替代方案",
                "06_保修维修与备件/备件等待与替代方案.md", ("action.query_spare_part",),
                ("备件等待", "备件")),
    ServiceRule("WARRANTY-PROOF", "序列号与购买凭证",
                "06_保修维修与备件/序列号与购买凭证.md", ("action.verify_purchase_credential",),
                ("购买凭证", "没有发票", "无发票")),
    ServiceRule("REPAIR-FLOW", "检测与维修流程",
                "06_保修维修与备件/检测与维修流程.md",
                ("action.register_repair", "action.repair_or_replace", "action.return_device"),
                ("维修流程", "检测流程")),
    # 05 里没有规则码的两篇：其余三篇正文自己引用了 RETURN-/QUALITY-/REFUND- 规则码，
    # 靠别名回填即可命中，不需要再建一个同义实体。
    ServiceRule("RETURN-DISPUTE-REVIEW", "检测争议与例外处理",
                "05_退换货与退款/检测争议与例外处理.md", ("action.reinspect",),
                ("检测争议", "检测复核")),
    ServiceRule("RETURN-SHIPPING-COST", "退换货费用与运费承担",
                "05_退换货与退款/费用与运费承担.md", (),
                ("退货运费", "运费承担")),
)

# 流程类动作：有业务副作用，但四期没有对应工具，一律 handling=true
SERVICE_ACTIONS: dict[str, str] = {
    "action.quote_and_confirm": "报价并取得用户确认",
    "action.query_spare_part": "查询备件库存与到货时间",
    "action.verify_purchase_credential": "核验购买凭证与序列号",
    "action.register_repair": "收件登记",
    "action.repair_or_replace": "维修或换件",
    "action.return_device": "质检后寄回",
    "action.reinspect": "检测复核",
}


def _ensure_entity(db: Session, *, code: str, kind: str, name: str, attrs: dict,
                   status: str = "DRAFT") -> Entity:
    row = db.execute(select(Entity).where(
        Entity.tenant_id == settings.tenant_id, Entity.code == code)).scalar_one_or_none()
    if row is None:
        row = Entity(tenant_id=settings.tenant_id, code=code, kind=kind, name=name,
                     attrs=attrs, status=status, source="manual")
        db.add(row)
        db.flush()
    else:
        merged = dict(row.attrs or {})
        merged.update(attrs)
        row.attrs = merged
        row.name = name or row.name
        db.add(row)
    return row


def _ensure_alias(db: Session, entity: Entity, alias: str, status: str = "DRAFT") -> None:
    exists = db.execute(select(Alias.id).where(
        Alias.tenant_id == settings.tenant_id, Alias.entity_id == entity.id,
        Alias.alias == alias)).scalar_one_or_none()
    if exists is None:
        db.add(Alias(tenant_id=settings.tenant_id, entity_id=entity.id, alias=alias,
                     confidence="HIGH", status=status, source="manual"))


def _ensure_relation(db: Session, src: Entity, predicate: str, dst: Entity, attrs: dict,
                     product_scope: str | None = None) -> bool:
    row = db.execute(select(Relation).where(
        Relation.tenant_id == settings.tenant_id, Relation.src_entity_id == src.id,
        Relation.predicate == predicate, Relation.dst_entity_id == dst.id)).scalar_one_or_none()
    if row is not None:
        if product_scope and row.product_scope != product_scope:
            row.product_scope = product_scope
            db.add(row)
        return False
    db.add(Relation(tenant_id=settings.tenant_id, src_entity_id=src.id, dst_entity_id=dst.id,
                    predicate=predicate, product_scope=product_scope, attrs=attrs,
                    status="DRAFT", source="manual"))
    return True


def _part_for(text: str) -> str | None:
    for rule in PART_RULES:
        if any(word in text for word in rule.keywords):
            return rule.part_code
    return None


def _remedies_for(text: str) -> list[str]:
    """同一段正文可能同时提到多种处置，全部收下（宁多勿漏，反正要审核）。"""
    found: list[str] = []
    for code, words in REMEDY_RULES:
        if any(word in text for word in words):
            found.append(code)
    return found


def _doc_title(path: Path) -> str | None:
    """读 front matter 的 title：它才是文档在检索里的自然叫法，用作实体名/别名。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("title:"):
            return line.split(":", 1)[1].strip().strip('"') or None
    return None


def _doc_sections(path: Path) -> list[tuple[str, int, list[str]]]:
    """按二级标题切分，返回 (标题, 起始行号, 正文行)。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    sections: list[tuple[str, int, list[str]]] = []
    current: tuple[str, int, list[str]] | None = None
    for index, line in enumerate(lines, start=1):
        match = HEADING_RE.match(line)
        if match:
            if current is not None:
                sections.append(current)
            current = (match.group(1), index, [])
        elif current is not None:
            current[2].append(line)
    if current is not None:
        sections.append(current)
    return sections


def extract_candidates(db: Session, actor: dict) -> dict:
    """抽取故障现象 → 部件归属 + 处置动作；幂等，全部 DRAFT。"""
    before_e = len(db.execute(select(Entity.id).where(Entity.tenant_id == settings.tenant_id)).scalars().all())
    before_r = len(db.execute(select(Relation.id).where(Relation.tenant_id == settings.tenant_id)).scalars().all())
    created_symptom = created_relation = 0
    skipped: list[dict] = []
    notes: list[dict] = []

    for code, name in HANDLING_ACTIONS.items():
        _ensure_entity(db, code=code, kind="action", name=name,
                       attrs={"handling": True, "tool": None}, status="DRAFT")

    for doc in sorted(PRODUCT_DOCS.glob("*/故障诊断.md")):
        product_code = doc.parent.name.split("_", 1)[0]
        for order, (heading, line_no, body) in enumerate(_doc_sections(doc), start=1):
            text = heading + "\n" + "\n".join(body)
            code = "SYM-" + product_code + "-" + str(order).zfill(2)
            existed = db.execute(select(Entity.id).where(
                Entity.tenant_id == settings.tenant_id, Entity.code == code)).scalar_one_or_none()
            symptom = _ensure_entity(
                db, code=code, kind="fault", name=heading,
                attrs={"product": product_code, "source_doc": str(doc.relative_to(ROOT)),
                       "source_line": line_no, "heading": heading},
                status="DRAFT")
            _ensure_alias(db, symptom, heading)
            if existed is None:
                created_symptom += 1
            part_code = _part_for(text)
            if part_code is None:
                skipped.append({"code": code, "heading": heading, "reason": "无部件关键词"})
            else:
                part = db.execute(select(Entity).where(
                    Entity.tenant_id == settings.tenant_id, Entity.code == part_code,
                    Entity.kind == "part")).scalar_one_or_none()
                if part is None:
                    skipped.append({"code": code, "heading": heading, "reason": "部件实体不存在：" + part_code})
                elif _ensure_relation(db, symptom, "SYMPTOM_OF", part,
                                      {"method": "keyword", "source_line": line_no},
                                      product_scope=product_code):
                    created_relation += 1
            remedies = _remedies_for(text)
            if not remedies:
                skipped.append({"code": code, "heading": heading, "reason": "无处置动作关键词"})
            for remedy in remedies:
                action = db.execute(select(Entity).where(
                    Entity.tenant_id == settings.tenant_id, Entity.code == remedy,
                    Entity.kind == "action")).scalar_one_or_none()
                if action is not None and _ensure_relation(
                        db, symptom, "REMEDY", action,
                        {"method": "keyword", "source_line": line_no},
                        product_scope=product_code):
                    created_relation += 1
            notes.append({"code": code, "heading": heading, "part": part_code, "remedy": remedies})

    # 06 服务政策：文档 → 政策实体 → 动作（GOVERNED_BY）
    for code, name in SERVICE_ACTIONS.items():
        _ensure_entity(db, code=code, kind="action", name=name,
                       attrs={"handling": True, "tool": None, "display_from": "service_flow"},
                       status="DRAFT")
    for rule in SERVICE_RULES:
        doc_path = ROOT / "knowledge_raw" / rule.doc
        if not doc_path.exists():
            skipped.append({"code": rule.code, "reason": "文档不存在：" + rule.doc})
            continue
        title = _doc_title(doc_path) or rule.name
        policy = _ensure_entity(db, code=rule.code, kind="policy", name=title,
                                attrs={"policy_kind": "policy", "source_doc": rule.doc},
                                status="DRAFT")
        if title != rule.name:
            _ensure_alias(db, policy, rule.name, status="APPROVED")
        for alias in rule.aliases:
            _ensure_alias(db, policy, alias, status="APPROVED")
        for action_code in rule.actions:
            action = db.execute(select(Entity).where(
                Entity.tenant_id == settings.tenant_id, Entity.code == action_code,
                Entity.kind == "action")).scalar_one_or_none()
            if action is None:
                skipped.append({"code": action_code, "reason": "动作实体不存在"})
                continue
            if _ensure_relation(db, action, "GOVERNED_BY", policy,
                                {"method": "doc_rule", "source_doc": rule.doc}):
                created_relation += 1

    db.flush()
    after_e = len(db.execute(select(Entity.id).where(Entity.tenant_id == settings.tenant_id)).scalars().all())
    after_r = len(db.execute(select(Relation.id).where(Relation.tenant_id == settings.tenant_id)).scalars().all())
    audit.record(db, actor, "ontology.extract", "ontology.entity", None,
                 after={"entities": after_e, "relations": after_r})
    db.commit()
    return {
        "total_entity": after_e, "total_relation": after_r,
        "new_entity": after_e - before_e, "new_relation": after_r - before_r,
        "symptom_new": created_symptom, "relation_new": created_relation,
        "notes": notes, "skipped": skipped,
    }
