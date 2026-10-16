"""支付网关适配器。一期为 MOCK 实现，切换真实渠道只需替换本模块。"""
import hmac
import hashlib

from app.core.config import settings


def create_payment(payment_no: str, amount: str, method: str, subject: str) -> dict:
    return {
        "payment_no": payment_no,
        "pay_url": f"https://pay.mock.local/{payment_no}?amount={amount}",
        "provider": settings.payment_provider,
        "method": method,
        "subject": subject,
    }


def sign(payload: str, secret: str | None = None) -> str:
    key = (secret or settings.jwt_secret).encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def verify_signature(payload: str, signature: str) -> bool:
    return hmac.compare_digest(sign(payload), signature or "")


def refund(refund_no: str, payment_no: str | None, amount: str) -> dict:
    return {"refund_no": refund_no, "channel_refund_no": "MOCK-RF-" + refund_no[-8:], "amount": amount,
            "status": "SUCCESS", "payment_no": payment_no}
