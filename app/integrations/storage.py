"""对象存储适配器：一期为本地文件系统实现，生产可替换为 S3/MinIO。"""
import hashlib
import pathlib
import uuid
from datetime import datetime

from app.core.config import settings
from app.core.errors import ValidationError

ALLOWED = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAGIC = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"%PDF-": "application/pdf",
    b"RIFF": "image/webp",
}


def base_dir() -> pathlib.Path:
    root = pathlib.Path(settings.storage_local_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def validate(file_name: str, content_type: str | None, payload: bytes) -> str:
    suffix = pathlib.Path(file_name).suffix.lower()
    if suffix not in ALLOWED:
        raise ValidationError(f"不支持的文件类型 {suffix or '未知'}，允许：{', '.join(sorted(ALLOWED))}")
    limit = settings.max_upload_mb * 1024 * 1024
    if len(payload) == 0:
        raise ValidationError("文件内容为空")
    if len(payload) > limit:
        raise ValidationError(f"文件超过 {settings.max_upload_mb}MB 上限")
    expected = ALLOWED[suffix]
    if content_type and content_type not in (expected, "application/octet-stream"):
        raise ValidationError(f"文件 MIME 与扩展名不一致：{content_type} != {expected}")
    for magic, mime in MAGIC.items():
        if payload.startswith(magic) and mime != expected:
            raise ValidationError("文件内容与扩展名不匹配")
    return expected


def save(file_name: str, payload: bytes, owner_type: str = "misc") -> dict:
    suffix = pathlib.Path(file_name).suffix.lower()
    stamp = datetime.now().strftime("%Y/%m")
    key = f"{settings.tenant_id}/{owner_type}/{stamp}/{uuid.uuid4().hex}{suffix}"
    target = base_dir() / key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return {"storage_key": key, "checksum": hashlib.sha256(payload).hexdigest(), "size": len(payload)}


def path_of(storage_key: str) -> pathlib.Path:
    root = base_dir().resolve()
    target = (root / storage_key).resolve()
    if not str(target).startswith(str(root)):
        raise ValidationError("非法的存储路径")
    return target


def exists(storage_key: str) -> bool:
    return path_of(storage_key).is_file()


def delete(storage_key: str) -> None:
    target = path_of(storage_key)
    if target.is_file():
        target.unlink()
