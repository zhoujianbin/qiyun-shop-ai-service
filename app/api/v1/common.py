from fastapi import Request
from sqlalchemy.orm import Session

from app.api.deps import visible_channel_ids
from app.models import AppUser
from app.services.customer import profile_of


def actor_of(request: Request, user: AppUser, db: Session) -> dict:
    customer_id = None
    if user.party in ("CUSTOMER", "GUEST"):
        customer_id = profile_of(db, user).id
    actor = {
        "id": user.id,
        "party": user.party,
        "label": user.display_name,
        "request_id": getattr(request.state, "request_id", None),
        "customer_id": customer_id,
        "is_super_admin": user.is_super_admin,
        "channel_ids": None,
    }
    if user.party == "STAFF":
        actor["channel_ids"] = visible_channel_ids(request, db, user)
    return actor
