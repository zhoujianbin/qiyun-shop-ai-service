from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AuditLog, OutboxEvent


def record(db: Session, actor: dict | None, action: str, resource_type: str, resource_id=None,
           before=None, after=None, channel_account_id=None) -> None:
    actor = actor or {}
    db.add(AuditLog(
        tenant_id=settings.tenant_id,
        actor_type=actor.get("party", "SYSTEM"),
        actor_id=actor.get("id"),
        actor_label=actor.get("label"),
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        channel_account_id=channel_account_id,
        before_data=before,
        after_data=after,
        request_id=actor.get("request_id"),
    ))


def emit(db: Session, event_type: str, aggregate_type: str, aggregate_id, payload: dict, request_id=None) -> None:
    db.add(OutboxEvent(
        tenant_id=settings.tenant_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        payload=payload,
        request_id=request_id,
    ))
