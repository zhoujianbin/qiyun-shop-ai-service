import itertools
import time
from datetime import datetime, timezone
from decimal import Decimal

from app.core.errors import NotFound


def now() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value):
    """把前端的 ISO 字符串统一解析为带时区 datetime。"""
    if isinstance(value, datetime):
        return value
    if not value:
        return now()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return now()


def list_payload(items, page: int = 1, page_size: int | None = None, total: int | None = None) -> dict:
    """统一列表响应：{items, page, page_size, total, meta}。"""
    size = page_size if page_size is not None else len(items)
    count = total if total is not None else len(items)
    return {"items": items, "page": page, "page_size": size, "total": count,
            "meta": {"page": page, "page_size": size, "total": count}}


def money(value) -> str | None:
    return None if value is None else f"{Decimal(value):.2f}"


def dt(value):
    return value.isoformat() if value else None


_SEQ_COUNTER = itertools.count(1)


def seq(prefix: str, digits: int = 3) -> str:
    """生成业务单号：前缀 + 秒级时间 + 毫秒 + 进程内自增序列，保证高并发下不重复。"""
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    millis = f"{int(time.time() * 1000) % 1000:03d}"
    counter = f"{next(_SEQ_COUNTER) % (10 ** digits):0{digits}d}"
    return prefix + stamp + millis + counter


def page_offset(page: int, page_size: int) -> tuple[int, int]:
    return (page - 1) * page_size, page_size


def get_or_404(db, model, pk, message: str = "资源不存在或不可见"):
    obj = db.get(model, pk)
    if obj is None:
        raise NotFound(message)
    return obj
