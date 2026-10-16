"""物流适配器：一期为 MOCK，返回可预测的轨迹模板。"""
from datetime import timedelta

from app.services.common import now


def query_tracking(tracking_no: str, carrier_code: str) -> list[dict]:
    base = now() - timedelta(days=1)
    return [
        {"event_time": (base - timedelta(hours=6)).isoformat(), "status": "PICKED_UP", "description": f"{carrier_code} 已揽收", "location": "发货仓"},
        {"event_time": base.isoformat(), "status": "IN_TRANSIT", "description": "快件已到达中转中心", "location": "中转场"},
    ]


def tracking_url(template: str | None, tracking_no: str) -> str | None:
    return template.replace("{tracking_no}", tracking_no) if template else None
