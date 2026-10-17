"""测试夹具：独立测试库、真实 schema、真实服务层数据、TestClient。"""
import os
import pathlib
import re
import uuid

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _test_db_name(base_url: str) -> str:
    """测试库名：TEST_DB 环境变量优先，否则由业务库名派生（xxx_dev -> xxx_test）。

    多人共用同一个 PostgreSQL 实例时，各自用不同的业务库名即可自动得到不同的测试库，
    避免并发执行 pytest 时互相 DROP DATABASE / CREATE DATABASE。
    """
    explicit = os.environ.get("TEST_DB")
    if explicit:
        return explicit
    name = base_url.rstrip("/").rsplit("/", 1)[-1]
    derived = re.sub(r"_dev", "_test", name, count=1)
    if derived == name:  # 库名不含 _dev 时派生不出测试库，绝不能落到业务库上
        raise RuntimeError(
            f"业务库名 {name!r} 不含 _dev，测试库无法派生；"
            "请把 DATABASE_URL 指向 xxx_dev_* 或显式设置 TEST_DB"
        )
    return derived


def _base_dsn() -> str:
    env_file = ROOT / ".env"
    url = None
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip()
    url = os.environ.get("DATABASE_URL", url)
    if not url:
        raise RuntimeError("缺少 DATABASE_URL，无法初始化测试库")
    return url


BASE_URL = _base_dsn()
TEST_DB = _test_db_name(BASE_URL)
TEST_URL = re.sub(r"/([^/]+)$", "/" + TEST_DB, BASE_URL)
os.environ["DATABASE_URL"] = TEST_URL
os.environ["APP_ENV"] = "test"
os.environ["LOG_LEVEL"] = "ERROR"

import psycopg  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from scripts import bootstrap  # noqa: E402


def _server_dsns() -> list[str]:
    """维护连接候选：优先 postgres 库（业务库可能尚未创建）。"""
    base = re.sub(r"\+psycopg", "", BASE_URL)
    return [re.sub(r"/([^/]+)$", "/" + name, base) for name in ("postgres", BASE_URL.rstrip("/").rsplit("/", 1)[-1])]


def _connect_admin():
    last: Exception | None = None
    for dsn in _server_dsns():
        try:
            return psycopg.connect(dsn, autocommit=True)
        except psycopg.OperationalError as exc:
            last = exc
    raise RuntimeError(f"无法连接 PostgreSQL 维护库：{last}")


def _test_dsn() -> str:
    return re.sub(r"\+psycopg", "", TEST_URL)


def _seed_ontology(db) -> None:
    """四期：测试库也要有本体数据，否则归一/图遍历类断言永远为空。"""
    from sqlalchemy import text

    from app.services import ontology, ontology_extract, ontology_review

    actor = {"id": None, "party": "SYSTEM", "label": "conftest"}
    ontology.import_structured_rules(db, actor)
    ontology_extract.extract_candidates(db, actor)
    ontology_review.apply_review(db, actor)
    draft_ids = [row[0] for row in db.execute(
        text("select id from ontology.entity where status = 'DRAFT'")).fetchall()]
    if draft_ids:
        ontology.review(db, actor, entity_ids=draft_ids, action="approve")
    # 只补审 DRAFT：DEPRECATED 是审核结论，不能被批量通过重新激活
    fault_ids = [row[0] for row in db.execute(
        text("select id from ontology.entity where kind = 'fault'"
             " and status = 'DRAFT'")).fetchall()]
    if fault_ids:
        ontology.review(db, actor, entity_ids=fault_ids, action="approve")


@pytest.fixture(scope="session", autouse=True)
def prepared_database():
    with _connect_admin() as conn:
        with conn.cursor() as cur:
            cur.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname = %s", (TEST_DB,))
            cur.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}"')
            cur.execute(f'CREATE DATABASE "{TEST_DB}"')
    schema = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8")
    with psycopg.connect(_test_dsn(), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(schema)
    with SessionLocal() as db:
        bootstrap.bootstrap_reference(db)
        bootstrap.bootstrap_catalog(db)
        bootstrap.bootstrap_customers(db)
        _seed_ontology(db)
    engine.dispose()
    yield


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def login(client: TestClient, username: str, password: str = "Qiyun@2026#Dev", staff: bool = True) -> str:
    path = "/api/v1/auth/staff/login" if staff else "/api/v1/auth/customer/login"
    resp = client.post(path, json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth(token: str, idem: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    if idem is not None:
        headers["Idempotency-Key"] = idem
    return headers


def new_key() -> str:
    return uuid.uuid4().hex


def staff_token(client: TestClient, username: str = "admin") -> str:
    return login(client, username, staff=True)


def customer_token(client: TestClient, username: str = "buyer_zhang") -> str:
    return login(client, username, staff=False)

@pytest.fixture(autouse=True)
def _relax_message_rate_limit(monkeypatch):
    """测试里同一客户会连发很多条消息，默认 20 条/分钟的限流会误伤用例。

    需要验证限流的用例显式把该值改小，因此这里统一放宽。
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "assistant_rate_limit_per_minute", 100_000)
