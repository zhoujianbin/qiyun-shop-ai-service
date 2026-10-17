"""四期本体审核：把规则结论与人工结论落库，可重复执行。

四类显式清单：
- REJECT_EDGES        明确判否的关系 → DEPRECATED（带 reason）
- WARN_EDGES          存疑但保留 → 打 review=warn
- DEPRECATE_ENTITIES  与其它实体同义、或来源反证的实体 → 整个实体下线（关系与别名随之下线）
- MANUAL_EDGES        人工补链 → APPROVED（带 reason 与产品范围）

一条派生规则（不维护清单，按语义自动生效）：
- 通用安全事件（无 product 属性且有 ESCALATES_TO）不挂具体部件。
  它们跨产品成立，绑到某个部件后图遍历会把"相机冒烟"推到"门锁锁体保修"。
"""
REJECT_EDGES = [
    ("SYMPTOM_OF", "SYM-QC-C2G-01", "lock_body_and_electronics", "摄像头配网/加密属通信配置；lock_body_and_electronics 是门锁部件，跨产品串台"),
    ("SYMPTOM_OF", "SYM-QC-C2G-03", "lock_body_and_electronics", "陌生访问属账户安全域；与门锁锁体电子部件无关"),
    ("SYMPTOM_OF", "SYM-QL-L3P-01", "battery", "battery 在保修规则中只挂 QR-R5M；门锁电量应关联 QA-L3-BAT8 或锁体，跨产品串台"),
    ("SYMPTOM_OF", "SYM-QR-R5M-03", "battery", "该症状主体是积水与电气危险并升级 ESC-P0-ELECTRICAL；仅\"电池起火\"一词命中，整体不归属电池"),
    ("SYMPTOM_OF", "SYM-QR-R5M-04", "battery", "原文明确无焦味且无电池异常才走该分支；来源反证与电池无关"),
    ("REMEDY", "SYM-QL-L3P-01", "action.collect_evidence", "原文的凭证指开锁凭证；并未要求收集订单号与现场凭证"),
]

WARN_EDGES = [
    ("REMEDY", "SYM-QL-L3P-02", "action.collect_evidence", "其他凭证同为开锁凭证语义；正文只要求清洁/重新录入/建工单"),
]

# 实体下线：(code, 理由)
DEPRECATE_ENTITIES = [
    ("SYM-QC-C2G-03",
     "与 unknown_camera_access 同义（同为\"陌生访问\"）；唯一 REMEDY 来自原文\"客服不得自行打开画面验证\"里的\"客服\"一词，"
     "属禁止性语句误命中。保留通用安全事件 + ESC-P1-CAMERA 已覆盖该场景"),
]

# 人工补链：(predicate, src_code, dst_code, product_scope, 理由)
MANUAL_EDGES = [
    ("SYMPTOM_OF", "SYM-QL-L3P-01", "lock_body_and_electronics", "QL-L3P",
     "人工补链：无法开锁对应锁体及电子部件；原文要求检查电量/应急供电/凭证/门体受力，并禁止暴力拆锁。"
     "原 battery 归属被否后该故障曾无部件可挂"),
]

UNSCOPED_ESCALATION_REASON = (
    "通用安全事件（无 product 属性且有 ESCALATES_TO）不挂具体部件："
    "它们是跨产品的安全事件，绑到部件会把保修推断串到别的产品"
)


def apply_review(db, actor) -> dict:
    """把审核结论落库：reject → DEPRECATED，warn → 保留但打标，人工结论 → APPROVED。"""
    from sqlalchemy import select, text

    from app.core.config import settings
    from app.models.generated import Entity, Relation
    from app.services import audit

    def find_entity(code: str):
        return db.execute(select(Entity).where(
            Entity.tenant_id == settings.tenant_id, Entity.code == code)).scalar_one_or_none()

    def find(predicate: str, src_code: str, dst_code: str):
        src = find_entity(src_code)
        dst = find_entity(dst_code)
        if src is None or dst is None:
            return None
        return db.execute(select(Relation).where(
            Relation.tenant_id == settings.tenant_id, Relation.src_entity_id == src.id,
            Relation.predicate == predicate, Relation.dst_entity_id == dst.id)).scalar_one_or_none()

    rejected = warned = missing = 0
    for predicate, src_code, dst_code, reason in REJECT_EDGES:
        row = find(predicate, src_code, dst_code)
        if row is None:
            missing += 1
            continue
        row.status = "DEPRECATED"
        row.attrs = {**(row.attrs or {}), "review": "reject", "review_reason": reason}
        db.add(row)
        rejected += 1
    for predicate, src_code, dst_code, reason in WARN_EDGES:
        row = find(predicate, src_code, dst_code)
        if row is None:
            missing += 1
            continue
        row.attrs = {**(row.attrs or {}), "review": "warn", "review_reason": reason}
        db.add(row)
        warned += 1

    deprecated = 0
    for code, reason in DEPRECATE_ENTITIES:
        entity = find_entity(code)
        if entity is None:
            missing += 1
            continue
        entity.status = "DEPRECATED"
        entity.attrs = {**(entity.attrs or {}), "review": "reject", "review_reason": reason}
        db.add(entity)
        db.execute(text(
            "UPDATE ontology.alias SET status = 'DEPRECATED' WHERE tenant_id = :t AND entity_id = :id"),
            {"t": settings.tenant_id, "id": entity.id})
        db.execute(text(
            "UPDATE ontology.relation SET status = 'DEPRECATED' WHERE tenant_id = :t"
            " AND (src_entity_id = :id OR dst_entity_id = :id)"),
            {"t": settings.tenant_id, "id": entity.id})
        deprecated += 1

    manual = 0
    for predicate, src_code, dst_code, scope, reason in MANUAL_EDGES:
        src, dst = find_entity(src_code), find_entity(dst_code)
        if src is None or dst is None:
            missing += 1
            continue
        row = find(predicate, src_code, dst_code)
        if row is None:
            row = Relation(tenant_id=settings.tenant_id, src_entity_id=src.id,
                           dst_entity_id=dst.id, predicate=predicate, product_scope=scope,
                           attrs={}, status="APPROVED", source="manual")
            db.add(row)
        row.status = "APPROVED"
        row.product_scope = scope
        row.attrs = {**(row.attrs or {}), "method": "manual", "review": "manual",
                     "review_reason": reason}
        manual += 1

    pruned = db.execute(text("""
        UPDATE ontology.relation r
        SET status = 'DEPRECATED',
            attrs = coalesce(r.attrs, '{}'::jsonb) || jsonb_build_object(
                'review', 'reject', 'review_reason', CAST(:reason AS text))
        FROM ontology.entity s
        WHERE s.id = r.src_entity_id
          AND r.tenant_id = :tenant
          AND r.predicate = 'SYMPTOM_OF'
          AND r.status = 'APPROVED'
          AND (s.attrs->>'product') IS NULL
          AND EXISTS (SELECT 1 FROM ontology.relation e
                      WHERE e.src_entity_id = s.id AND e.predicate = 'ESCALATES_TO'
                        AND e.status = 'APPROVED')
        RETURNING r.id
    """), {"tenant": settings.tenant_id, "reason": UNSCOPED_ESCALATION_REASON}).fetchall()

    audit.record(db, actor, "ontology.review.ai", "ontology.relation", None,
                 after={"rejected": rejected, "warned": warned, "missing": missing,
                        "deprecated_entities": deprecated, "manual_edges": manual,
                        "pruned_unscoped": len(pruned)})
    db.commit()
    return {"rejected": rejected, "warned": warned, "missing": missing,
            "deprecated_entities": deprecated, "manual_edges": manual,
            "pruned_unscoped": len(pruned)}
