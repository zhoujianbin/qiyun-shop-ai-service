from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Conflict, NotFound, ValidationError
from app.models import Invoice, Order
from app.services import audit
from app.services.common import get_or_404, money, now, page_offset, seq


def _view(i: Invoice) -> dict:
    return {"id": i.id, "invoice_no": i.invoice_no, "order_id": i.order_id, "customer_id": i.customer_id,
            "type": i.type, "title_type": i.title_type, "title": i.title, "tax_no": i.tax_no,
            "content": i.content, "amount": money(i.amount), "tax_amount": None, "status": i.status,
            "file_url": i.file_url, "attachment_id": None, "issue_type": "BLUE",
            "bank_name": None, "bank_account_masked": None, "registered_address": None,
            "registered_phone_masked": None, "email": None, "remark": i.remark,
            "issued_at": i.issued_at.isoformat() if i.issued_at else None,
            "voided_at": i.voided_at.isoformat() if i.voided_at else None,
            "created_at": i.created_at.isoformat(), "updated_at": i.updated_at.isoformat(), "version": i.version}


def apply(db: Session, actor: dict, payload: dict) -> dict:
    order = get_or_404(db, Order, payload["order_id"], "订单不存在")
    if actor.get("party") in ("CUSTOMER", "GUEST") and order.customer_id != actor.get("customer_id"):
        raise NotFound("订单不存在")
    if order.payment_status not in ("PAID", "PARTIAL_REFUNDED"):
        raise Conflict("INVOICE_NOT_ALLOWED", "订单未支付，不能开票")
    tax_no = payload.get("tax_no")
    title_type = payload.get("title_type") or ("COMPANY" if tax_no else "PERSONAL")
    if title_type == "COMPANY" and (not tax_no or len(tax_no) < 15):
        raise ValidationError("企业抬头必须提供 15 位以上税号")
    invoice = Invoice(tenant_id=settings.tenant_id, order_id=order.id, customer_id=order.customer_id,
                      type=payload.get("type", "ELECTRONIC"), title_type=title_type, title=payload["title"],
                      tax_no=tax_no, content=payload.get("content") or payload.get("remark") or "商品明细",
                      amount=payload.get("amount") or order.paid_amount, status="REQUESTED")
    db.add(invoice)
    db.flush()
    audit.record(db, actor, "invoice_apply", "invoice", invoice.id, after={"title": invoice.title},
                 channel_account_id=order.channel_account_id)
    db.commit()
    return _view(invoice)


def list_invoices(db: Session, actor: dict, *, page: int, page_size: int, status: str | None = None) -> dict:
    stmt = select(Invoice).where(Invoice.tenant_id == settings.tenant_id)
    if actor.get("party") in ("CUSTOMER", "GUEST"):
        stmt = stmt.where(Invoice.customer_id == actor.get("customer_id"))
    else:
        channel_ids = actor.get("channel_ids")
        if channel_ids is not None:
            if not channel_ids:
                stmt = stmt.where(Invoice.id < 0)
            else:
                stmt = stmt.join(Order, Order.id == Invoice.order_id).where(Order.channel_account_id.in_(channel_ids))
    if status:
        stmt = stmt.where(Invoice.status == status)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    offset, limit = page_offset(page, page_size)
    rows = db.execute(stmt.order_by(Invoice.created_at.desc()).offset(offset).limit(limit)).scalars().all()
    return {"page": page, "page_size": page_size, "total": total, "meta": {"page": page, "page_size": page_size, "total": total},
            "items": [_view(i) for i in rows]}


def get_invoice(db: Session, actor: dict, invoice_id: int) -> dict:
    invoice = get_or_404(db, Invoice, invoice_id, "发票不存在")
    if actor.get("party") in ("CUSTOMER", "GUEST") and invoice.customer_id != actor.get("customer_id"):
        raise NotFound("发票不存在")
    return _view(invoice)


def issue(db: Session, actor: dict, invoice_id: int, payload: dict) -> dict:
    invoice = get_or_404(db, Invoice, invoice_id, "发票不存在")
    if invoice.status == "ISSUED":
        return _view(invoice)
    if invoice.status not in ("REQUESTED", "FAILED"):
        raise Conflict("INVOICE_STATE_INVALID", f"发票状态 {invoice.status} 不能开具")
    invoice.invoice_no = payload.get("invoice_no") or seq("INV")
    invoice.status = "ISSUED"
    invoice.issued_at = now()
    invoice.file_url = payload.get("file_url") or f"https://invoice.local/{invoice.invoice_no}.pdf"
    audit.record(db, actor, "invoice_issue", "invoice", invoice.id, after={"invoice_no": invoice.invoice_no})
    db.commit()
    return _view(invoice)


def void(db: Session, actor: dict, invoice_id: int, reason: str | None = None) -> dict:
    invoice = get_or_404(db, Invoice, invoice_id, "发票不存在")
    if invoice.status not in ("ISSUED", "REQUESTED"):
        raise Conflict("INVOICE_STATE_INVALID", f"发票状态 {invoice.status} 不能作废")
    invoice.status = "VOIDED"
    invoice.voided_at = now()
    audit.record(db, actor, "invoice_void", "invoice", invoice.id, after={"reason": reason})
    db.commit()
    return _view(invoice)
