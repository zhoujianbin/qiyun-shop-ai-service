import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import request_id_ctx, setup_logging
from app.core.middleware import IdempotencyMiddleware, RequestContextMiddleware

setup_logging()
logger = logging.getLogger("app")

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="栖云智家第一期企业电商基础平台 API",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id", "Idempotent-Replay"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "message": exc.message, "details": exc.details, "request_id": request_id_ctx.get()},
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"code": "VALIDATION_FAILED", "message": "字段校验失败", "details": exc.errors(), "request_id": request_id_ctx.get()},
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": "服务器内部错误", "details": None, "request_id": request_id_ctx.get()},
    )


@app.get("/api/v1/system/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "version": settings.app_version, "env": settings.app_env}


@app.get("/api/v1/system/version", tags=["system"])
def version() -> dict:
    return {"name": settings.app_name, "version": settings.app_version, "tenant_id": settings.tenant_id}


from app.api.v1.router import api_router  # noqa: E402

app.include_router(api_router, prefix="/api/v1")

# ---------------- 前端静态资源（构建产物存在时启用） ----------------
import pathlib  # noqa: E402

from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

WEB_DIST = pathlib.Path(__file__).resolve().parents[1] / "web" / "dist"

if WEB_DIST.is_dir():
    app.mount("/static/dist", StaticFiles(directory=str(WEB_DIST)), name="web-assets")

    RESERVED_PREFIXES = ("api/", "docs", "redoc", "openapi.json", "static/")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        """SPA 客户端路由回退：静态文件优先，其余交给 index.html；API 路径保持 404。"""
        if full_path.startswith(RESERVED_PREFIXES):
            raise HTTPException(status_code=404, detail="Not Found")
        if full_path:
            candidate = WEB_DIST / full_path
            if candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(WEB_DIST / "index.html")
