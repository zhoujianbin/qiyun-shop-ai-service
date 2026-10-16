import hashlib
import json
import logging
import time
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import new_request_id, now_ms, request_id_ctx

logger = logging.getLogger("app.request")

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
EXEMPT_PREFIXES = ("/api/v1/auth", "/api/v1/attachments", "/api/v1/webhooks", "/docs", "/openapi.json", "/api/v1/system")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-Id") or new_request_id()
        request_id_ctx.set(rid)
        request.state.request_id = rid
        started = now_ms()
        response = await call_next(request)
        duration = round(now_ms() - started, 2)
        response.headers["X-Request-Id"] = rid
        logger.info(
            "request",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status": response.status_code,
                "duration_ms": duration,
                "user_id": getattr(request.state, "user_id", None),
            },
        )
        return response


def _error(code: str, message: str, status: int, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"code": code, "message": message, "details": None, "request_id": request_id},
    )


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """写接口幂等：同 key 同指纹回放，已存在不同指纹返回 409。"""

    async def dispatch(self, request: Request, call_next):
        if request.method not in WRITE_METHODS or request.url.path.startswith(EXEMPT_PREFIXES):
            return await call_next(request)
        key = request.headers.get("Idempotency-Key")
        if not key:
            return _error("MISSING_IDEMPOTENCY_KEY", "写接口必须携带 Idempotency-Key", 400, request_id_ctx.get())
        body = await request.body()
        fingerprint = hashlib.sha256(
            (request.method + request.url.path + "?" + request.url.query).encode() + b"|" + body
        ).hexdigest()
        user_id = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            try:
                user_id = int(jwt.decode(auth[7:], settings.jwt_secret, algorithms=[settings.jwt_algorithm])["sub"])
            except Exception:
                user_id = None

        from app.core.db import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as db:
            row = db.execute(
                text("select id, request_hash, state, response_status, response_body, user_id from shared.idempotency_record where tenant_id=:t and idem_key=:k"),
                {"t": settings.tenant_id, "k": key},
            ).mappings().first()
            if row:
                if row["request_hash"] != fingerprint or (row["user_id"] and user_id and row["user_id"] != user_id):
                    return _error("IDEMPOTENCY_CONFLICT", "同一幂等键的请求内容不一致", 409, request_id_ctx.get())
                if row["state"] == "COMPLETED":
                    return JSONResponse(
                        status_code=row["response_status"] or 200,
                        content=row["response_body"],
                        headers={"Idempotent-Replay": "true", "X-Request-Id": request_id_ctx.get()},
                    )
                if row["state"] == "IN_PROGRESS":
                    return _error("IDEMPOTENCY_IN_PROGRESS", "相同请求正在处理中，请稍后查询结果", 409, request_id_ctx.get())
                db.execute(text("delete from shared.idempotency_record where id=:i"), {"i": row["id"]})
                db.commit()
            db.execute(
                text("""insert into shared.idempotency_record
                        (tenant_id, idem_key, user_id, method, path, request_hash, state, expires_at)
                        values (:t, :k, :u, :m, :p, :h, 'IN_PROGRESS', :e)"""),
                {"t": settings.tenant_id, "k": key, "u": user_id, "m": request.method, "p": request.url.path,
                 "h": fingerprint, "e": datetime.now(timezone.utc) + timedelta(hours=24)},
            )
            db.commit()

        response = await call_next(request)
        if response.headers.get("content-type", "").startswith("text/event-stream"):
            return response
        chunks = [chunk async for chunk in response.body_iterator]
        raw = b"".join(chunks)
        status = response.status_code
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else None
        except Exception:
            payload = None
        with SessionLocal() as db:
            if 200 <= status < 300:
                db.execute(
                    text("""update shared.idempotency_record set state='COMPLETED', response_status=:s,
                            response_body=cast(:b as jsonb), completed_at=now()
                            where tenant_id=:t and idem_key=:k"""),
                    {"s": status, "b": json.dumps(payload, ensure_ascii=False) if payload is not None else None,
                     "t": settings.tenant_id, "k": key},
                )
            else:
                db.execute(
                    text("delete from shared.idempotency_record where tenant_id=:t and idem_key=:k"),
                    {"t": settings.tenant_id, "k": key},
                )
            db.commit()
        return Response(
            content=raw,
            status_code=status,
            headers={k: v for k, v in response.headers.items() if k.lower() != "content-length"},
            media_type=response.media_type,
        )
