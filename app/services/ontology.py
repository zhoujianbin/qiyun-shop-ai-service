"""四期本体服务：实体/关系/别名维护、结构化规则导入、切片映射、实体归一与图遍历。

边界：
- 只写 ontology schema，不碰 knowledge/commerce/shared 的任何既有表。
- 检索集成只产出二期已支持的过滤键（product_scope/category），不改 knowledge_retrieval。
- 只有 APPROVED 的实体/关系/别名参与归一回填与图遍历。
"""
from __future__ import annotations

import logging
import re
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Conflict, NotFound, ValidationError
from app.models.generated import (
    Alias, ChunkEntity, Entity, EntityTag, Relation,
)
from app.services import audit
from app.services.common import list_payload, now

logger = logging.getLogger(__name__)

KINDS = ("product", "accessory", "part", "fault", "action", "policy")

# 政策编码的中文名：每条都能指到一份知识文档（只是翻译规则 id，不改规则本身）
# ESC-P3-GENERAL 的 triggers 是"受理分类"，不是故障现象，导入时跳过
PLACEHOLDER_TRIGGERS = {"general_question", "cosmetic_issue", "suggestion"}

POLICY_LABELS = {
    "ESC-P3-GENERAL": "P3 一般咨询（不升级）",           # escalation_matrix.yaml：P3/frontline_support
    "RETURN-NO-REASON-7D": "七日无理由退货",           # 05_退换货与退款/七日无理由退货.md
    "QUALITY-ISSUE-RETURN-15D": "质量问题退货（15 日内）",   # 05_退换货与退款/质量问题退换货.md
    "QUALITY-ISSUE-EXCHANGE-30D": "质量问题换货（30 日内）",  # 同上
    "REFUND-MERCHANT-PROCESS-3BD": "退款审核与 3 个工作日处理",  # 05_退换货与退款/退款处理与到账.md
    "SHIPPING-FREE-99": "满 99 元免运费",              # 03_物流与履约/发货时效与运费.md
    "LOGISTICS-STAGNANT-72H": "物流停滞 72 小时处理",    # 03_物流与履约/物流停滞丢件与拒收.md
    "ADDRESS-CHANGE-AFTER-SHIP": "发货后改地址与物流拦截",  # 03_物流与履约/地址修改与物流拦截.md
    "INSTALL-RESCHEDULE-4H": "安装改约需提前 4 小时",      # 04_安装与交付/服务范围与预约.md
    "CLOUD-COOLING-OFF-7D": "云服务取消退款 7 天冷静期",   # 08_云服务与订阅/取消退款与冷静期.md
}

# 部件编码的中文名，来自 KB-WARRANTY-001《产品与部件保修矩阵》（只是翻译，不是新规则）
PART_LABELS = {
    "lock_body_and_electronics": "锁体及电子部件",
    "lock_cylinder": "锁芯",
    "main_unit": "主机",
    "robot_and_dock": "主机及基站",
    "battery": "电池",
    "lamp_and_driver": "灯体及驱动",
}
PREDICATES = ("PART_OF", "SYMPTOM_OF", "REMEDY", "COVERED_BY", "GOVERNED_BY", "ESCALATES_TO", "ALIAS_OF")
STATUSES = ("DRAFT", "APPROVED", "DEPRECATED")
MAX_DEPTH = 2
RULES_DIR = Path(__file__).resolve().parents[2] / "knowledge_raw" / "13_结构化规则"


# ---------------------------------------------------------------- 视图
def entity_view(row: Entity) -> dict:
    return {
        "id": row.id, "code": row.code, "kind": row.kind, "name": row.name,
        "summary": row.summary, "attrs": row.attrs or {}, "status": row.status,
        "source": row.source,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def relation_view(row: Relation, src: Entity | None = None, dst: Entity | None = None) -> dict:
    return {
        "id": row.id, "predicate": row.predicate,
        "src_entity_id": row.src_entity_id, "dst_entity_id": row.dst_entity_id,
        "src_code": src.code if src is not None else None,
        "dst_code": dst.code if dst is not None else None,
        "product_scope": row.product_scope,
        "weight": str(row.weight) if isinstance(row.weight, Decimal) else row.weight,
        "status": row.status, "source": row.source, "attrs": row.attrs or {},
    }


def alias_view(row: Alias) -> dict:
    return {
        "id": row.id, "entity_id": row.entity_id, "alias": row.alias,
        "confidence": row.confidence, "status": row.status, "source": row.source,
    }


# ---------------------------------------------------------------- 实体 CRUD
def _entity(db: Session, entity_id: int) -> Entity:
    row = db.get(Entity, entity_id)
    if row is None or row.tenant_id != settings.tenant_id:
        raise NotFound("实体不存在")
    return row


def _action_code(value: str) -> str:
    value = str(value or "").strip()
    return value if value.startswith("action.") else f"action.{value}" if value else ""


def _product_entity(db: Session, code: str) -> Entity | None:
    return db.execute(select(Entity).where(
        Entity.tenant_id == settings.tenant_id, Entity.code == code,
        Entity.kind == "product")).scalar_one_or_none()


def list_entities(db: Session, *, kind: str | None = None, status: str | None = None,
                  keyword: str | None = None, page: int = 1, page_size: int = 20) -> dict:
    stmt = select(Entity).where(Entity.tenant_id == settings.tenant_id)
    if kind:
        if kind not in KINDS:
            raise ValidationError(f"实体类型不合法：{kind}")
        stmt = stmt.where(Entity.kind == kind)
    if status:
        stmt = stmt.where(Entity.status == status.upper())
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(Entity.code.ilike(pattern) | Entity.name.ilike(pattern))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.order_by(Entity.kind, Entity.code)
                      .offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return list_payload([entity_view(r) for r in rows], page, page_size, total)


def get_entity(db: Session, entity_id: int) -> dict:
    row = _entity(db, entity_id)
    tags = db.execute(select(EntityTag).where(EntityTag.entity_id == row.id)).scalars().all()
    aliases = db.execute(select(Alias).where(Alias.entity_id == row.id)).scalars().all()
    view = entity_view(row)
    view["tags"] = [{"tag": t.tag, "value": t.value} for t in tags]
    view["aliases"] = [alias_view(a) for a in aliases]
    return view


def create_entity(db: Session, actor: dict, payload: dict) -> dict:
    kind = payload.get("kind")
    if kind not in KINDS:
        raise ValidationError(f"实体类型不合法：{kind}")
    code = (payload.get("code") or "").strip()
    if not code:
        raise ValidationError("实体编码不能为空")
    exists = db.execute(select(Entity.id).where(
        Entity.tenant_id == settings.tenant_id, Entity.code == code)).scalar_one_or_none()
    if exists:
        raise Conflict("ENTITY_CODE_EXISTS", f"实体编码已存在：{code}")
    row = Entity(
        tenant_id=settings.tenant_id, code=code, kind=kind,
        name=(payload.get("name") or code).strip(),
        summary=payload.get("summary"), attrs=payload.get("attrs") or {},
        status=(payload.get("status") or "DRAFT").upper(), source="manual",
    )
    db.add(row)
    db.flush()
    audit.record(db, actor, "ontology.entity.create", "ontology.entity", row.id,
                 after={"code": code, "kind": kind})
    db.commit()
    return entity_view(row)


def update_entity(db: Session, actor: dict, entity_id: int, payload: dict) -> dict:
    row = _entity(db, entity_id)
    before = {"name": row.name, "status": row.status}
    if "name" in payload and payload["name"]:
        row.name = payload["name"].strip()
    if "summary" in payload:
        row.summary = payload["summary"]
    if "attrs" in payload and payload["attrs"] is not None:
        row.attrs = payload["attrs"]
    if "status" in payload and payload["status"]:
        status = payload["status"].upper()
        if status not in STATUSES:
            raise ValidationError(f"状态不合法：{status}")
        row.status = status
    db.add(row)
    audit.record(db, actor, "ontology.entity.update", "ontology.entity", row.id, before=before,
                 after={"name": row.name, "status": row.status})
    db.commit()
    return entity_view(row)


# ---------------------------------------------------------------- 关系
def list_relations(db: Session, *, entity_id: int | None = None, predicate: str | None = None,
                   status: str | None = None, product_scope: str | None = None,
                   page: int = 1, page_size: int = 50) -> dict:
    stmt = select(Relation).where(Relation.tenant_id == settings.tenant_id)
    if product_scope:
        stmt = stmt.where(Relation.product_scope == product_scope)
    if entity_id:
        stmt = stmt.where((Relation.src_entity_id == entity_id) | (Relation.dst_entity_id == entity_id))
    if predicate:
        if predicate not in PREDICATES:
            raise ValidationError(f"谓词不合法：{predicate}")
        stmt = stmt.where(Relation.predicate == predicate)
    if status:
        stmt = stmt.where(Relation.status == status.upper())
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.order_by(Relation.id)
                      .offset((page - 1) * page_size).limit(page_size)).scalars().all()
    codes = {e.id: e for e in db.execute(
        select(Entity).where(Entity.id.in_({r.src_entity_id for r in rows} | {r.dst_entity_id for r in rows}))
    ).scalars().all()} if rows else {}
    return list_payload([relation_view(r, codes.get(r.src_entity_id), codes.get(r.dst_entity_id)) for r in rows],
                        page, page_size, total)


def upsert_relation(db: Session, actor: dict, payload: dict) -> dict:
    predicate = (payload.get("predicate") or "").upper()
    if predicate not in PREDICATES:
        raise ValidationError(f"谓词不合法：{predicate}")
    src = _entity(db, int(payload["src_entity_id"]))
    dst = _entity(db, int(payload["dst_entity_id"]))
    if src.id == dst.id:
        raise ValidationError("关系的起点与终点不能相同")
    scope = (payload.get("product_scope") or "").strip() or None
    if scope is not None and _product_entity(db, scope) is None:
        raise ValidationError(f"product_scope 不是已存在的产品编码：{scope}")
    row = db.execute(select(Relation).where(
        Relation.tenant_id == settings.tenant_id, Relation.src_entity_id == src.id,
        Relation.predicate == predicate, Relation.dst_entity_id == dst.id)).scalar_one_or_none()
    if row is None:
        row = Relation(tenant_id=settings.tenant_id, src_entity_id=src.id, dst_entity_id=dst.id,
                       predicate=predicate, product_scope=scope,
                       weight=Decimal(str(payload.get("weight") or 1)),
                       attrs=payload.get("attrs") or {},
                       status=(payload.get("status") or "DRAFT").upper(), source="manual")
        db.add(row)
    else:
        if "product_scope" in payload:
            row.product_scope = scope
        if "weight" in payload and payload["weight"] is not None:
            row.weight = Decimal(str(payload["weight"]))
        if "attrs" in payload and payload["attrs"] is not None:
            row.attrs = payload["attrs"]
        if payload.get("status"):
            row.status = payload["status"].upper()
        db.add(row)
    db.flush()
    audit.record(db, actor, "ontology.relation.upsert", "ontology.relation", row.id,
                 after={"predicate": predicate, "src": src.code, "dst": dst.code})
    db.commit()
    return relation_view(row, src, dst)


# ---------------------------------------------------------------- 别名
def list_aliases(db: Session, *, entity_id: int | None = None, keyword: str | None = None,
                 page: int = 1, page_size: int = 50) -> dict:
    stmt = select(Alias).where(Alias.tenant_id == settings.tenant_id)
    if entity_id:
        stmt = stmt.where(Alias.entity_id == entity_id)
    if keyword:
        stmt = stmt.where(Alias.alias.ilike(f"%{keyword}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.order_by(Alias.entity_id, Alias.alias)
                      .offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return list_payload([alias_view(r) for r in rows], page, page_size, total)


def upsert_alias(db: Session, actor: dict, payload: dict) -> dict:
    entity = _entity(db, int(payload["entity_id"]))
    alias = (payload.get("alias") or "").strip()
    if not alias:
        raise ValidationError("别名不能为空")
    row = db.execute(select(Alias).where(
        Alias.tenant_id == settings.tenant_id, Alias.entity_id == entity.id,
        Alias.alias == alias)).scalar_one_or_none()
    if row is None:
        row = Alias(tenant_id=settings.tenant_id, entity_id=entity.id, alias=alias,
                    confidence=(payload.get("confidence") or "HIGH").upper(),
                    status=(payload.get("status") or "DRAFT").upper(), source="manual")
        db.add(row)
    else:
        if payload.get("confidence"):
            row.confidence = payload["confidence"].upper()
        if payload.get("status"):
            row.status = payload["status"].upper()
        db.add(row)
    db.flush()
    audit.record(db, actor, "ontology.alias.upsert", "ontology.alias", row.id,
                 after={"entity": entity.code, "alias": alias})
    db.commit()
    return alias_view(row)


# ---------------------------------------------------------------- 审核
def review(db: Session, actor: dict, *, entity_ids: list[int], action: str = "approve") -> dict:
    """批量审核：approve(DRAFT→APPROVED) / deprecate(→DEPRECATED)。"""
    if action not in ("approve", "deprecate"):
        raise ValidationError("审核动作只能是 approve 或 deprecate")
    target = "APPROVED" if action == "approve" else "DEPRECATED"
    rows = db.execute(select(Entity).where(
        Entity.tenant_id == settings.tenant_id, Entity.id.in_(entity_ids))).scalars().all()
    if not rows:
        raise NotFound("没有可审核的实体")
    changed = []
    for row in rows:
        row.status = target
        db.add(row)
        changed.append(row.code)
    # 实体的关系与别名随之生效/失效，保持"只有 APPROVED 参与"的语义一致
    db.execute(
        text("UPDATE ontology.relation SET status = :s WHERE tenant_id = :t"
             " AND (src_entity_id = ANY(:ids) OR dst_entity_id = ANY(:ids)) AND status <> 'DEPRECATED'"),
        {"s": target, "t": settings.tenant_id, "ids": [r.id for r in rows]},
    )
    db.execute(
        text("UPDATE ontology.alias SET status = :s WHERE tenant_id = :t"
             " AND entity_id = ANY(:ids) AND status <> 'DEPRECATED'"),
        {"s": target, "t": settings.tenant_id, "ids": [r.id for r in rows]},
    )
    audit.record(db, actor, f"ontology.review.{action}", "ontology.entity", None,
                 after={"codes": changed})
    db.commit()
    return {"updated": len(rows), "status": target, "codes": changed}


# ---------------------------------------------------------------- 实体归一
def _approved_alias_map(db: Session) -> list[tuple[str, Entity]]:
    rows = db.execute(
        select(Alias.alias, Entity).join(Entity, Entity.id == Alias.entity_id).where(
            Alias.tenant_id == settings.tenant_id, Alias.status == "APPROVED",
            Entity.status == "APPROVED")
    ).all()
    pairs = [(alias, entity) for alias, entity in rows]
    # 直接命中编码与名称也算
    entities = db.execute(select(Entity).where(
        Entity.tenant_id == settings.tenant_id, Entity.status == "APPROVED")).scalars().all()
    for entity in entities:
        pairs.append((entity.code, entity))
        pairs.append((entity.name, entity))
    return sorted(pairs, key=lambda item: len(item[0]), reverse=True)


def _tags_of(db: Session, entity_ids: list[int]) -> dict[int, dict[str, str]]:
    if not entity_ids:
        return {}
    rows = db.execute(select(EntityTag).where(EntityTag.entity_id.in_(entity_ids))).scalars().all()
    result: dict[int, dict[str, str]] = {}
    for row in rows:
        result.setdefault(row.entity_id, {})[row.tag] = row.value
    return result


def _product_scope_of(entity: Entity, tags: dict[int, dict[str, str]],
                      parent_scopes: dict[int, set[str]]) -> str | None:
    """把实体映射为二期已支持的 product_scope。

    产品直接取编码，故障取自身 product 属性，部件/配件只在**唯一**归属某产品时才收窄。
    main_unit 同时属于 QC-C2G 与 QH-G1，这类跨产品共用编码必须返回 None——
    返回其中任意一个都会把检索错误地锁到别的产品上。
    """
    tag = tags.get(entity.id, {}).get("product_scope")
    if tag:
        return tag
    if entity.kind == "product":
        return entity.code
    if entity.kind == "fault":
        product_code = (entity.attrs or {}).get("product")
        if product_code:
            return str(product_code)
    if entity.kind in ("part", "accessory"):
        scopes = parent_scopes.get(entity.id) or set()
        if len(scopes) == 1:
            return next(iter(scopes))
    return None


FUZZY_MIN_SCORE = 0.6      # 覆盖率阈值（交集 / 较短一方）
FUZZY_MIN_SHARED = 2       # 至少共享两个二元组，避免单词巧合
FUZZY_MIN_LEN = 4
BOOST_STOPWORDS = {"智能", "产品", "设备", "栖云", "家用"}
CJK_RUN = re.compile(r"[\u4e00-\u9fa5]{2,}")


def _bigrams(text: str) -> set[str]:
    cleaned = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", text or "")
    return {cleaned[i:i + 2] for i in range(len(cleaned) - 1)}


def _fuzzy_entity(db: Session, question: str) -> Entity | None:
    """2-gram 兜底：唯一最优且达阈值才采纳；并列一律放弃。"""
    if len(question) < FUZZY_MIN_LEN:
        return None
    target = _bigrams(question)
    if not target:
        return None
    entities = db.execute(select(Entity).where(
        Entity.tenant_id == settings.tenant_id, Entity.status == "APPROVED")).scalars().all()
    if not entities:
        return None
    aliases: dict[int, list[str]] = {}
    for alias, entity in _approved_alias_map(db):
        aliases.setdefault(entity.id, []).append(alias)

    scored: list[tuple[float, Entity]] = []
    for entity in entities:
        candidates = {entity.code, entity.name, *aliases.get(entity.id, [])}
        best = 0.0
        for candidate in candidates:
            grams = _bigrams(candidate)
            if not grams:
                continue
            shared = len(target & grams)
            if shared < FUZZY_MIN_SHARED:
                continue
            # 覆盖率而非 Jaccard：问题里常带"怎么办"这类附加词，Jaccard 会被稀释
            score = shared / min(len(target), len(grams))
            best = max(best, score)
        if best >= FUZZY_MIN_SCORE:
            scored.append((best, entity))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    top_score = scored[0][0]
    winners = [entity for score, entity in scored if score == top_score]
    return winners[0] if len(winners) == 1 else None


# ---------------------------------------------------------------- 向量兜底（仅排序）
VECTOR_MIN_SCORE = 0.52      # 实测：0.52 + 0.05 间距能收下"指纹录不进去/扫地机不回充"，且不误收 */

VECTOR_MIN_MARGIN = 0.05
_ENTITY_VECTOR_CACHE: dict[str, object] = {"key": None, "items": []}


def _entity_vectors(db: Session) -> list[tuple[Entity, list[float]]]:
    """实体向量缓存：按 (实体数, 最大 updated_at) 判活，进程内复用。

    只用于排序兜底，错了最多是顺序微调，不会改变可见范围。
    """
    entities = db.execute(select(Entity).where(
        Entity.tenant_id == settings.tenant_id, Entity.status == "APPROVED")).scalars().all()
    if not entities:
        return []
    latest = max((item.updated_at for item in entities if item.updated_at), default=None)
    key = (len(entities), latest)
    if _ENTITY_VECTOR_CACHE["key"] == key:
        return _ENTITY_VECTOR_CACHE["items"]  # type: ignore[return-value]
    try:
        from app.integrations import embedding

        aliases: dict[int, list[str]] = {}
        for alias, entity_id in db.execute(select(Alias.alias, Alias.entity_id).where(
                Alias.status == "APPROVED")).fetchall():
            aliases.setdefault(entity_id, []).append(alias)
        docs = [f"{item.name} {' '.join(aliases.get(item.id, [])[:4])} {item.code}".strip()
                for item in entities]
        vectors = embedding.encode_documents(docs)
        items = list(zip(entities, vectors))
        _ENTITY_VECTOR_CACHE.update({"key": key, "items": items})
        return items
    except Exception as exc:  # noqa: BLE001 - 向量兜底不可用就跳过
        logger.warning("实体向量缓存构建失败，跳过向量兜底：%s", exc)
        return []


def _vector_entity(db: Session, question: str) -> Entity | None:
    """第三层兜底：唯一最优、分数 ≥0.55 且与次优差 ≥0.05 才采纳。"""
    items = _entity_vectors(db)
    if not items:
        return None
    try:
        from app.integrations import embedding

        vector = embedding.encode_query(question)
    except Exception as exc:  # noqa: BLE001
        logger.warning("问题向量化失败，跳过向量兜底：%s", exc)
        return None
    scored = sorted(((sum(a * b for a, b in zip(vector, item_vector)), entity)
                     for entity, item_vector in items), key=lambda pair: pair[0], reverse=True)
    if len(scored) < 2:
        return None
    best_score, best_entity = scored[0]
    second_score = scored[1][0]
    if best_score < VECTOR_MIN_SCORE or (best_score - second_score) < VECTOR_MIN_MARGIN:
        return None
    return best_entity


def _boost_products(db: Session, question: str) -> list[Entity]:
    """产品名的宽松命中：只用于排序加权，绝不参与过滤。"""
    products = db.execute(select(Entity).where(
        Entity.tenant_id == settings.tenant_id, Entity.status == "APPROVED",
        Entity.kind == "product")).scalars().all()
    hits: list[Entity] = []
    for entity in products:
        for run in CJK_RUN.findall(entity.name or ""):
            matched = False
            for size in range(len(run), 1, -1):
                for start in range(0, len(run) - size + 1):
                    token = run[start:start + size]
                    if token in BOOST_STOPWORDS:
                        continue
                    if token in question:
                        matched = True
                        break
                if matched:
                    break
            if matched:
                hits.append(entity)
                break
    return hits


def normalize_question(db: Session, question: str, *, max_entities: int = 3) -> dict:
    """问题 → 实体（先精确最长匹配，再 2-gram 兜底）→ 二期可用的 product_scope。

    另返回 boost_entities（产品名宽松命中，仅用于排序）。
    零命中时返回空，调用方据此退化为原样检索。
    """
    text_value = (question or "").strip()
    if not text_value:
        return {"entities": [], "entity_ids": [], "product_scope": None,
                "method": None, "boost_entities": []}
    pairs = _approved_alias_map(db)
    taken: list[tuple[int, int]] = []
    matched: list[dict] = []
    seen_codes: set[str] = set()

    def overlaps(start: int, end: int) -> bool:
        return any(not (end <= s or start >= e) for s, e in taken)

    for alias, entity in pairs:
        if not alias or entity.code in seen_codes:
            continue
        start = text_value.find(alias)
        if start < 0:
            continue
        end = start + len(alias)
        if overlaps(start, end):
            continue
        taken.append((start, end))
        seen_codes.add(entity.code)
        matched.append({"id": entity.id, "code": entity.code, "kind": entity.kind,
                        "name": entity.name, "matched": alias})
        if len(matched) >= max_entities:
            break
    method = "exact" if matched else None
    if not matched:
        fuzzy = _fuzzy_entity(db, text_value)
        if fuzzy is not None:
            matched = [{"id": fuzzy.id, "code": fuzzy.code, "kind": fuzzy.kind,
                        "name": fuzzy.name, "matched": fuzzy.name, "method": "fuzzy"}]
            method = "fuzzy"
    boost = _boost_products(db, text_value)
    boost_codes = {item.code for item in boost}
    # 第三层兜底：向量相似度只加进 boost（仅排序），不参与过滤也不改 product_scope
    vector_hit = _vector_entity(db, text_value)
    if vector_hit is not None and vector_hit.code not in boost_codes:
        boost.append(vector_hit)
        boost_codes.add(vector_hit.code)
    boost_payload = [{"id": item.id, "code": item.code, "name": item.name} for item in boost]
    if not matched:
        return {"entities": [], "entity_ids": [], "product_scope": None,
                "method": None, "boost_entities": boost_payload}

    ids = [item["id"] for item in matched]
    tags = _tags_of(db, ids)
    neighbors = db.execute(select(Relation).where(
        Relation.tenant_id == settings.tenant_id, Relation.status == "APPROVED",
        (Relation.src_entity_id.in_(ids)) | (Relation.dst_entity_id.in_(ids)))).scalars().all()
    other_ids = {r.src_entity_id for r in neighbors} | {r.dst_entity_id for r in neighbors}
    other_ids -= set(ids)
    nodes = {e.id: e for e in db.execute(
        select(Entity).where(Entity.id.in_(set(ids) | other_ids))).scalars().all()}
    # 部件/配件的归属产品集合：只有 PART_OF 且另一端确实是产品才算数
    parent_scopes: dict[int, set[str]] = {}
    for relation in neighbors:
        if relation.predicate != "PART_OF":
            continue
        src_node = nodes.get(relation.src_entity_id)
        dst_node = nodes.get(relation.dst_entity_id)
        if src_node is None or dst_node is None or dst_node.kind != "product":
            continue
        parent_scopes.setdefault(src_node.id, set()).add(dst_node.code)

    # 范围优先级：产品 > 故障 > 部件/配件。命中更高优先层后不再用低优先层兜底，
    # 否则"电池鼓包"会因为命中部件 battery 而被错误收窄到 QR-R5M。
    rows = {e.id: e for e in db.execute(select(Entity).where(Entity.id.in_(ids))).scalars().all()}
    resolved = [(rows[item["id"]].kind, _product_scope_of(rows[item["id"]], tags, parent_scopes))
                for item in matched if item["id"] in rows]
    product_scope = None
    if method == "exact":
        for kind in ("product", "fault", "part", "accessory"):
            if not any(item_kind == kind for item_kind, _ in resolved):
                continue
            product_scope = next((scope for item_kind, scope in resolved
                                  if item_kind == kind and scope), None)
            break
        # 只有"产品类"的宽松命中才能纠正范围（如"门锁电池"）；其它实体一律不许改写 scope
        product_boosts = [item for item in boost if item.kind == "product"]
        if product_boosts and product_scope not in {item.code for item in product_boosts}:
            product_scope = product_boosts[0].code
    return {"entities": matched, "entity_ids": ids, "product_scope": product_scope,
            "method": method, "boost_entities": boost_payload}


# ---------------------------------------------------------------- 图遍历
def graph(db: Session, entity_id: int, *, depth: int = 1,
          product_scope: str | None = None) -> dict:
    """无向、限深、带路径去重的邻域展开；depth 上限 2。

    传入 product_scope 时只走"跨产品通用（NULL）或本产品"的边，
    避免 SYM-QC-C2G-xx → main_unit → QH-G1 保修 这类跨产品保修推断。
    """
    root = _entity(db, entity_id)
    depth = max(1, min(int(depth), MAX_DEPTH))
    # 只在有范围时拼条件：NULL 参数在 PostgreSQL 里无法推断类型（AmbiguousParameter）
    scope_clause = ""
    params = {"root": root.id, "tenant": settings.tenant_id, "max_depth": depth}
    if product_scope:
        scope_clause = "AND (r.product_scope IS NULL OR r.product_scope = :scope)"
        params["scope"] = product_scope
    rows = db.execute(text(f"""
        WITH RECURSIVE walk(node_id, predicate, depth, path) AS (
            SELECT CASE WHEN r.src_entity_id = :root THEN r.dst_entity_id ELSE r.src_entity_id END,
                   r.predicate, 1, ARRAY[:root, CASE WHEN r.src_entity_id = :root
                                                     THEN r.dst_entity_id ELSE r.src_entity_id END]
            FROM ontology.relation r
            WHERE r.tenant_id = :tenant AND r.status = 'APPROVED'
              AND (r.src_entity_id = :root OR r.dst_entity_id = :root)
              {scope_clause}
            UNION ALL
            SELECT CASE WHEN r.src_entity_id = w.node_id THEN r.dst_entity_id ELSE r.src_entity_id END,
                   r.predicate, w.depth + 1,
                   w.path || CASE WHEN r.src_entity_id = w.node_id THEN r.dst_entity_id ELSE r.src_entity_id END
            FROM ontology.relation r
            JOIN walk w ON (r.src_entity_id = w.node_id OR r.dst_entity_id = w.node_id)
            WHERE r.tenant_id = :tenant AND r.status = 'APPROVED'
              {scope_clause}
              AND w.depth < :max_depth
              AND NOT (CASE WHEN r.src_entity_id = w.node_id THEN r.dst_entity_id ELSE r.src_entity_id END = ANY(w.path))
        )
        SELECT DISTINCT node_id, min(depth) AS depth, min(predicate) AS predicate
        FROM walk GROUP BY node_id ORDER BY depth, node_id
    """), params).mappings().all()
    node_ids = [root.id] + [row["node_id"] for row in rows]
    entities = {e.id: e for e in db.execute(select(Entity).where(Entity.id.in_(node_ids))).scalars().all()}
    return {
        "root": entity_view(root),
        "nodes": [{"entity": entity_view(entities[row["node_id"]]), "depth": row["depth"],
                   "via": row["predicate"]} for row in rows if row["node_id"] in entities],
        "edge_count": len(rows),
        "depth": depth,
        "product_scope": product_scope,
    }


# ---------------------------------------------------------------- 导入
def _load_yaml(name: str) -> dict:
    import yaml

    path = RULES_DIR / name
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _upsert_imported(db: Session, *, code: str, kind: str, name: str, summary: str | None = None,
                     attrs: dict | None = None) -> Entity:
    row = db.execute(select(Entity).where(
        Entity.tenant_id == settings.tenant_id, Entity.code == code)).scalar_one_or_none()
    if row is None:
        row = Entity(tenant_id=settings.tenant_id, code=code, kind=kind, name=name,
                     summary=summary, attrs=attrs or {}, status="APPROVED", source="import")
        db.add(row)
        db.flush()
    else:
        row.name = name or row.name
        row.summary = summary or row.summary
        if attrs:
            merged = dict(row.attrs or {})
            merged.update(attrs)
            row.attrs = merged
        db.add(row)
    return row


def _upsert_relation_imported(db: Session, src: Entity, predicate: str, dst: Entity,
                              attrs: dict | None = None,
                              product_scope: str | None = None) -> Relation:
    row = db.execute(select(Relation).where(
        Relation.tenant_id == settings.tenant_id, Relation.src_entity_id == src.id,
        Relation.predicate == predicate, Relation.dst_entity_id == dst.id)).scalar_one_or_none()
    if row is None:
        row = Relation(tenant_id=settings.tenant_id, src_entity_id=src.id, dst_entity_id=dst.id,
                       predicate=predicate, product_scope=product_scope,
                       attrs=attrs or {}, status="APPROVED", source="import")
        db.add(row)
        db.flush()
    elif product_scope and row.product_scope != product_scope:
        row.product_scope = product_scope
        db.add(row)
    return row


def import_structured_rules(db: Session, actor: dict) -> dict:
    """从 knowledge_raw/13_结构化规则 导入实体与关系；幂等（同 code 不重复插入）。"""
    created = {"entity": 0, "relation": 0}
    before_e = db.execute(select(func.count()).select_from(Entity).where(
        Entity.tenant_id == settings.tenant_id)).scalar_one()
    before_r = db.execute(select(func.count()).select_from(Relation).where(
        Relation.tenant_id == settings.tenant_id)).scalar_one()

    catalog = _load_yaml("product_catalog.yaml")
    warranty = _load_yaml("product_warranty.yaml")
    escalation = _load_yaml("escalation_matrix.yaml")
    policy = _load_yaml("policy_rules.yaml")

    products: dict[str, Entity] = {}
    for item in catalog.get("products") or []:
        code = str(item.get("product_id") or "").strip()
        if not code:
            continue
        entity = _upsert_imported(db, code=code, kind="product", name=str(item.get("name") or code),
                                  summary=f"产品主档：{item.get('master') or ''}".strip("：") or None,
                                  attrs={"product_type": item.get("type")})
        products[code] = entity
        tag = db.execute(select(EntityTag).where(
            EntityTag.tenant_id == settings.tenant_id, EntityTag.entity_id == entity.id,
            EntityTag.tag == "product_scope", EntityTag.value == code)).scalar_one_or_none()
        if tag is None:
            db.add(EntityTag(tenant_id=settings.tenant_id, entity_id=entity.id,
                             tag="product_scope", value=code))

    for item in catalog.get("accessories") or []:
        code = str(item.get("accessory_id") or "").strip()
        if not code:
            continue
        entity = _upsert_imported(db, code=code, kind="accessory",
                                  name=str(item.get("name") or code),
                                  attrs={"consumable": bool(item.get("consumable"))})
        parent = products.get(str(item.get("product_id") or ""))
        if parent is not None:
            _upsert_relation_imported(db, entity, "PART_OF", parent, product_scope=parent.code)

    parts: dict[str, Entity] = {}
    for item in warranty.get("rules") or []:
        rule_id = str(item.get("rule_id") or "").strip()
        component = str(item.get("component") or "").strip()
        product_code = str(item.get("product_id") or "").strip()
        if not rule_id or not component:
            continue
        part = parts.get(component)
        if part is None:
            part = _upsert_imported(db, code=component, kind="part",
                                    name=PART_LABELS.get(component, component))
            parts[component] = part
        months = item.get("months")
        component_cn = PART_LABELS.get(component, component)
        rule = _upsert_imported(db, code=rule_id, kind="policy",
                                name=f"{product_code} · {component_cn} 保修 {months} 个月",
                                attrs={"policy_kind": "warranty", "product_id": product_code,
                                       "component": component, "months": months})
        _upsert_relation_imported(db, part, "COVERED_BY", rule,
                                  attrs={"product_id": product_code},
                                  product_scope=product_code)
        parent = products.get(product_code)
        if parent is not None:
            _upsert_relation_imported(db, part, "PART_OF", parent, product_scope=parent.code)

    # 故障现象来自 escalation 触发词；中文展示名取别名表的第一条说法（业务可维护）
    aliases_yaml = _load_yaml("escalation_aliases.yaml")

    def fault_display(trigger: str) -> str:
        words = aliases_yaml.get(trigger) or []
        return str(words[0]) if words else str(trigger)

    # 升级矩阵本身作为政策实体
    for rule_id, spec in (escalation.get("rules") or {}).items():
        triggers_cn = [fault_display(str(t)) for t in (spec.get("triggers") or [])
                       if str(t) not in PLACEHOLDER_TRIGGERS]
        display = POLICY_LABELS.get(str(rule_id)) or (
            f"{spec.get('priority') or ''} 升级：{'/'.join(triggers_cn[:3]) or rule_id}".strip())
        rule = _upsert_imported(db, code=str(rule_id), kind="policy",
                                name=display,
                                attrs={"policy_kind": "escalation", "priority": spec.get("priority"),
                                       "response_minutes": spec.get("response_minutes"),
                                       "prohibit": spec.get("prohibit") or []})
        for trigger in spec.get("triggers") or []:
            if str(trigger) in PLACEHOLDER_TRIGGERS:
                continue
            fault = _upsert_imported(db, code=str(trigger), kind="fault",
                                     name=fault_display(str(trigger)),
                                     attrs={"display_from": "escalation_aliases"})
            _upsert_relation_imported(db, fault, "ESCALATES_TO", rule)

    # 政策里点名、但四期工具清单没有对应工具的处理动作：实体必须存在，
    # 否则 GOVERNED_BY 会指向一个不存在的动作（悬空引用）。
    for code, name in {"action.request_intercept_or_reroute": "物流拦截与改址"}.items():
        _upsert_imported(db, code=code, kind="action", name=name,
                         attrs={"tool": None, "handling": True})

    for rule_id, spec in (policy.get("rules") or {}).items():
        rule = _upsert_imported(db, code=str(rule_id), kind="policy",
                                name=POLICY_LABELS.get(str(rule_id), str(rule_id)),
                                attrs={"policy_kind": "policy",
                                       **(spec if isinstance(spec, dict) else {})})
        action_key = _action_code(spec.get("action")) if isinstance(spec, dict) else ""
        if not action_key:
            continue
        action = db.execute(select(Entity).where(
            Entity.tenant_id == settings.tenant_id, Entity.code == action_key,
            Entity.kind == "action")).scalar_one_or_none()
        if action is not None:
            _upsert_relation_imported(db, action, "GOVERNED_BY", rule)

    # 对话可触发的动作（与四期工具清单一一对应；语义由本仓库定义，不是业务规则）
    actions = {
        "action.query_product": "查询商品与参数",
        "action.query_order": "查询订单状态与明细",
        "action.query_shipment": "查询物流进度",
        "action.query_payment": "查询支付状态",
        "action.query_after_sales": "查询售后进度",
        "action.query_invoice": "查询发票状态",
    }
    for code, name in actions.items():
        _upsert_imported(db, code=code, kind="action", name=name, attrs={"tool": code.split(".", 1)[1]})

    # 故障现象的中文别名（来自 escalation_aliases.yaml，业务可维护）
    for fault_code, words in (aliases_yaml or {}).items():
        fault = db.execute(select(Entity).where(
            Entity.tenant_id == settings.tenant_id, Entity.code == str(fault_code),
            Entity.kind == "fault")).scalar_one_or_none()
        if fault is None:
            continue
        for word in words or []:
            exists = db.execute(select(Alias.id).where(
                Alias.tenant_id == settings.tenant_id, Alias.entity_id == fault.id,
                Alias.alias == str(word))).scalar_one_or_none()
            if exists is None:
                db.add(Alias(tenant_id=settings.tenant_id, entity_id=fault.id, alias=str(word),
                             confidence="HIGH", status="APPROVED", source="import"))

    # 清理历史上误当成故障导入的受理分类（幂等）
    stale = db.execute(select(Entity).where(
        Entity.tenant_id == settings.tenant_id, Entity.kind == "fault",
        Entity.code.in_(PLACEHOLDER_TRIGGERS))).scalars().all()
    for row in stale:
        db.delete(row)
    db.flush()

    after_e = db.execute(select(func.count()).select_from(Entity).where(
        Entity.tenant_id == settings.tenant_id)).scalar_one()
    after_r = db.execute(select(func.count()).select_from(Relation).where(
        Relation.tenant_id == settings.tenant_id)).scalar_one()
    created["entity"] = after_e - before_e
    created["relation"] = after_r - before_r
    audit.record(db, actor, "ontology.import", "ontology.entity", None,
                 after={"entities": after_e, "relations": after_r, **created})
    db.commit()
    return {"total_entity": after_e, "total_relation": after_r, **created}


# ---------------------------------------------------------------- 切片映射
def _resolve_entity(db: Session, entity_id: int) -> Entity:
    return _entity(db, entity_id)


def backfill_chunk_entities(db: Session, actor: dict, *, limit: int | None = None) -> dict:
    """按别名把已发布切片关联到实体；逻辑键(document_id, version, chunk_ord) 幂等。"""
    pairs = [(alias, entity) for alias, entity in _approved_alias_map(db) if len(alias) >= 2]
    if not pairs:
        return {"inserted": 0, "scanned": 0}
    sql = """
        SELECT ch.id AS chunk_id, ch.ord AS chunk_ord, ch.content, ch.title_path,
               dv.version, d.document_id
        FROM knowledge.chunk ch
        JOIN knowledge.document_version dv ON dv.id = ch.document_version_id
        JOIN knowledge.document d ON d.id = dv.document_pk
        WHERE dv.status = 'ACTIVE' AND ch.tenant_id = :tenant
        ORDER BY d.document_id, dv.version, ch.ord
    """
    rows = db.execute(text(sql), {"tenant": settings.tenant_id}).mappings().all()
    if limit:
        rows = rows[:limit]
    inserted = 0
    for row in rows:
        haystack = f"{row['title_path'] or ''}\n{row['content'] or ''}"
        hit_codes: set[int] = set()
        for alias, entity in pairs:
            if entity.id in hit_codes:
                continue
            if alias in haystack:
                hit_codes.add(entity.id)
                exists = db.execute(select(ChunkEntity.id).where(
                    ChunkEntity.document_id == row["document_id"],
                    ChunkEntity.version == row["version"],
                    ChunkEntity.chunk_ord == row["chunk_ord"],
                    ChunkEntity.entity_id == entity.id)).scalar_one_or_none()
                if exists:
                    continue
                db.add(ChunkEntity(
                    tenant_id=settings.tenant_id, document_id=row["document_id"],
                    version=row["version"], chunk_ord=row["chunk_ord"], chunk_id=row["chunk_id"],
                    entity_id=entity.id, method="alias", confidence="HIGH", status="APPROVED",
                ))
                inserted += 1
    audit.record(db, actor, "ontology.chunk_entity.backfill", "ontology.chunk_entity", None,
                 after={"inserted": inserted, "scanned": len(rows)})
    db.commit()
    return {"inserted": inserted, "scanned": len(rows)}


def backfill_product_scope(db: Session, actor: dict) -> dict:
    """把二期文档的 product_scope 补上：仅当该文档的切片只关联到一个产品实体。

    只写已有列的数据（不改表结构），且只填空值——已有值不动，可重复执行。
    """
    result = db.execute(text("""
        UPDATE knowledge.document d
        SET product_scope = sub.scope
        FROM (
            SELECT ce.document_id, min(e.code) AS scope
            FROM ontology.chunk_entity ce
            JOIN ontology.entity e ON e.id = ce.entity_id
            WHERE e.kind = 'product' AND ce.status = 'APPROVED' AND ce.tenant_id = :tenant
            GROUP BY ce.document_id
            HAVING count(DISTINCT e.code) = 1
        ) AS sub
        WHERE d.document_id = sub.document_id
          AND d.tenant_id = :tenant
          AND d.product_scope IS NULL
        RETURNING d.document_id
    """), {"tenant": settings.tenant_id}).fetchall()
    audit.record(db, actor, "ontology.product_scope.backfill", "knowledge.document", None,
                 after={"filled": len(result)})
    db.commit()
    return {"filled": len(result), "documents": [row[0] for row in result]}


def relink_chunks(db: Session, actor: dict) -> dict:
    """文档发新版后按逻辑键重挂：只更新 chunk_id，不重跑实体抽取。"""
    result = db.execute(text("""
        UPDATE ontology.chunk_entity ce
        SET chunk_id = ch.id
        FROM knowledge.chunk ch
        JOIN knowledge.document_version dv ON dv.id = ch.document_version_id
        JOIN knowledge.document d ON d.id = dv.document_pk
        WHERE ce.document_id = d.document_id
          AND ce.version = dv.version
          AND ce.chunk_ord = ch.ord
          AND ce.chunk_id IS DISTINCT FROM ch.id
        RETURNING ce.id
    """)).fetchall()
    audit.record(db, actor, "ontology.chunk_entity.relink", "ontology.chunk_entity", None,
                 after={"relinked": len(result)})
    db.commit()
    return {"relinked": len(result)}


def product_scope_covered(db: Session, scope: str | None) -> bool:
    """该产品范围在二期文档里是否真的有覆盖；没覆盖就不加过滤，避免把召回打成 0。"""
    if not scope:
        return False
    count = db.execute(text(
        "SELECT count(*) FROM knowledge.document d"
        " JOIN knowledge.document_version dv ON dv.document_pk = d.id"
        " WHERE d.product_scope = :scope AND dv.status = 'ACTIVE' AND d.tenant_id = :tenant"
    ), {"scope": scope, "tenant": settings.tenant_id}).scalar_one()
    return bool(count)


def chunk_entity_codes(db: Session, document_id: str | None, version: int | None,
                       chunk_ord: int | None) -> set[str]:
    if not document_id or version is None or chunk_ord is None:
        return set()
    rows = db.execute(
        select(Entity.code).join(ChunkEntity, ChunkEntity.entity_id == Entity.id).where(
            ChunkEntity.document_id == document_id, ChunkEntity.version == version,
            ChunkEntity.chunk_ord == chunk_ord, ChunkEntity.status == "APPROVED",
            Entity.status == "APPROVED")
    ).scalars().all()
    return set(rows)


def entities_of_chunk(db: Session, document_id: str, version: int, chunk_ord: int) -> list[Entity]:
    rows = db.execute(
        select(Entity).join(ChunkEntity, ChunkEntity.entity_id == Entity.id).where(
            ChunkEntity.document_id == document_id, ChunkEntity.version == version,
            ChunkEntity.chunk_ord == chunk_ord, ChunkEntity.status == "APPROVED",
            Entity.status == "APPROVED")
    ).scalars().all()
    return list(rows)
