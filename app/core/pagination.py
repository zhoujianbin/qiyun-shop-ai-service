from typing import Any

from pydantic import BaseModel, Field


class Page(BaseModel):
    page: int = 1
    page_size: int = Field(default=20, ge=1, le=100)
    total: int = 0
    items: list[Any] = []


def paginate(items: list[Any], page: int, page_size: int, total: int) -> dict:
    return {"page": page, "page_size": page_size, "total": total, "items": items}
