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
    ("SYMPTOM_OF", "electric_shock", "lock_body_and_electronics", "escalation 不含部件信息；触电是人身安全事件"),
    ("SYMPTOM_OF", "water_near_energized_equipment", "main_unit", "描述积水接近通电设备的环境危险而非主控部件故障"),
    ("SYMPTOM_OF", "smoke", "main_unit", "烟雾为设备级或环境级现象，未给出部件绑定"),
    ("SYMPTOM_OF", "sparks", "main_unit", "火花为电气故障现象，未给出部件绑定"),
]


def apply_review(db, actor) -> dict:
    """把子 agent 审核结论落库：reject → DEPRECATED，warn → 保留但打标。"""
    from sqlalchemy import select

    from app.core.config import settings
    from app.models.generated import Entity, Relation
    from app.services import audit

    def find(predicate: str, src_code: str, dst_code: str):
        src = db.execute(select(Entity).where(Entity.tenant_id == settings.tenant_id,
                                              Entity.code == src_code)).scalar_one_or_none()
        dst = db.execute(select(Entity).where(Entity.tenant_id == settings.tenant_id,
                                              Entity.code == dst_code)).scalar_one_or_none()
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
    audit.record(db, actor, "ontology.review.ai", "ontology.relation", None,
                 after={"rejected": rejected, "warned": warned, "missing": missing})
    db.commit()
    return {"rejected": rejected, "warned": warned, "missing": missing}
