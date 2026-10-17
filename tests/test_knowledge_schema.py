"""二期迁移与权限验收：表数、9 个新列、向量维度、12 个权限码、AUDITOR 收窄。"""
from sqlalchemy import text

from app.core.db import SessionLocal

NEW_COLUMNS = {
    ("knowledge", "chunk", "embedding_status"),
    ("knowledge", "chunk", "identity_level"),
    ("knowledge", "document", "identity_level"),
    ("knowledge", "document", "effective_date"),
    ("knowledge", "document_version", "change_summary"),
    ("knowledge", "document_version", "source_kind"),
    ("knowledge", "document_version", "published_at"),
    ("knowledge", "document_version", "published_by"),
    ("shared", "schema_migration", "checksum"),
}

NEW_TABLES = {
    "knowledge.rule",
    "knowledge.rule_conflict",
    "knowledge.review_task",
    "knowledge.review_comment",
    "knowledge.import_job",
    "knowledge.retrieval_log",
    "shared.schema_migration",
}


def test_base_table_count_is_68():
    with SessionLocal() as db:
        total = db.execute(text(
            "select count(*) from information_schema.tables"
            " where table_schema in ('shared','commerce','knowledge','assistant','ontology')"
            " and table_type = 'BASE TABLE'"
        )).scalar_one()
    # 一期 43 + 二期 12 = 55；三期 +6 = 61；四期 +5（ontology）+2（assistant）= 68
    assert total == 68


def test_new_tables_exist():
    with SessionLocal() as db:
        rows = db.execute(text(
            "select table_schema || '.' || table_name from information_schema.tables"
            " where table_schema in ('shared','commerce','knowledge') and table_type = 'BASE TABLE'"
        )).scalars().all()
    assert NEW_TABLES <= set(rows)


def test_new_columns_exist():
    with SessionLocal() as db:
        rows = set(
            tuple(row)
            for row in db.execute(text(
                "select table_schema, table_name, column_name from information_schema.columns"
                " where table_schema in ('shared','commerce','knowledge')"
            )).all()
        )
    assert NEW_COLUMNS <= rows


def test_embedding_is_512_and_indexed():
    with SessionLocal() as db:
        typ = db.execute(text(
            "select format_type(atttypid, atttypmod) from pg_attribute"
            " where attrelid = 'knowledge.chunk'::regclass and attname = 'embedding'"
        )).scalar_one()
        indexdef = db.execute(text(
            "select indexdef from pg_indexes where indexname = 'knowledge_chunk_hnsw_idx'"
        )).scalar_one()
    assert typ == "vector(512)"
    assert "hnsw" in indexdef and "vector_cosine_ops" in indexdef


def test_document_status_check_unchanged():
    """一期 CHECK 不改：待生效只在 document_version 上表达。"""
    with SessionLocal() as db:
        definition = db.execute(text(
            "select pg_get_constraintdef(oid) from pg_constraint where conname = 'knowledge_document_status_ck'"
        )).scalar_one()
    assert "SCHEDULED" not in definition
    for value in ("DRAFT", "REVIEWING", "ACTIVE", "ARCHIVED", "FAILED"):
        assert value in definition


def test_twelve_knowledge_permissions():
    with SessionLocal() as db:
        codes = db.execute(text(
            "select code from shared.app_permission where module = 'knowledge' order by code"
        )).scalars().all()
    assert len(codes) == 12
    assert all(code.startswith("knowledge:") for code in codes)


def test_new_roles_and_grants():
    with SessionLocal() as db:
        roles = set(db.execute(text("select code from shared.app_role")).scalars().all())
        admin_count = db.execute(text(
            "select count(*) from shared.app_role_permission rp"
            " join shared.app_role r on r.id = rp.role_id"
            " join shared.app_permission p on p.id = rp.permission_id"
            " where r.code = 'KNOWLEDGE_ADMIN' and p.code like 'knowledge:%'"
        )).scalar_one()
        supervisor = set(db.execute(text(
            "select p.code from shared.app_role_permission rp"
            " join shared.app_role r on r.id = rp.role_id"
            " join shared.app_permission p on p.id = rp.permission_id"
            " where r.code = 'CS_SUPERVISOR' and p.code like 'knowledge:%'"
        )).scalars().all())
    assert {"KNOWLEDGE_ADMIN", "KNOWLEDGE_REVIEWER", "KNOWLEDGE_EDITOR", "CS_AGENT"} <= roles
    assert admin_count == 12
    assert supervisor == {
        "knowledge:document:read", "knowledge:retrieval:test", "knowledge:governance:read",
    }


def test_auditor_has_no_knowledge_read():
    with SessionLocal() as db:
        count = db.execute(text(
            "select count(*) from shared.app_role_permission rp"
            " join shared.app_role r on r.id = rp.role_id"
            " join shared.app_permission p on p.id = rp.permission_id"
            " where r.code = 'AUDITOR' and p.code like 'knowledge:%'"
        )).scalar_one()
    assert count == 0


def test_schema_migration_table_is_unique_per_version():
    with SessionLocal() as db:
        exists = db.execute(text(
            "select count(*) from information_schema.tables"
            " where table_schema = 'shared' and table_name = 'schema_migration'"
        )).scalar_one()
        constraint = db.execute(text(
            "select pg_get_constraintdef(oid) from pg_constraint where conname = 'schema_migration_version_key'"
        )).scalar_one()
    assert exists == 1
    assert "UNIQUE" in constraint.upper()
