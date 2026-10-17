"""三期数据地基：assistant schema（四期 8 张表）、ai:* 权限码与坐席角色。"""
from sqlalchemy import text

from app.core.db import SessionLocal

ASSISTANT_TABLES = {
    "conversation", "message", "citation", "handoff", "identity_verification", "retrieval_trace",
    # 四期：待确认动作与工具调用留痕
    "pending_action", "tool_call",
}


def _scalar(sql: str):
    with SessionLocal() as db:
        return db.execute(text(sql)).scalar_one()


def test_assistant_schema_has_eight_tables():
    with SessionLocal() as db:
        rows = db.execute(text(
            "select table_name from information_schema.tables"
            " where table_schema = 'assistant' and table_type = 'BASE TABLE'"
        )).scalars().all()
    assert set(rows) == ASSISTANT_TABLES


def test_message_role_allows_agent_and_status_enum():
    role = _scalar("select pg_get_constraintdef(oid) from pg_constraint where conname='assistant_message_role_ck'")
    status = _scalar("select pg_get_constraintdef(oid) from pg_constraint where conname='assistant_message_status_ck'")
    assert "AGENT" in role
    for value in ("STREAMING", "DONE", "FAILED", "REFUSED"):
        assert value in status


def test_client_msg_id_unique_index():
    definition = _scalar("select indexdef from pg_indexes where indexname='assistant_message_client_uidx'")
    assert "UNIQUE" in definition.upper() and "client_msg_id" in definition


def test_handoff_single_open_per_conversation():
    definition = _scalar("select indexdef from pg_indexes where indexname='assistant_handoff_open_uidx'")
    assert "UNIQUE" in definition.upper() and "OPEN" in definition


def test_five_ai_permissions():
    with SessionLocal() as db:
        codes = db.execute(text(
            "select code from shared.app_permission where module='ai' order by code"
        )).scalars().all()
    assert codes == [
        "ai:chat:read", "ai:chat:write", "ai:handoff:read", "ai:handoff:write", "ai:trace:read",
    ]


def test_agent_roles_and_grants():
    with SessionLocal() as db:
        roles = set(db.execute(text("select code from shared.app_role")).scalars().all())
        agent = set(db.execute(text(
            "select p.code from shared.app_role_permission rp"
            " join shared.app_role r on r.id=rp.role_id"
            " join shared.app_permission p on p.id=rp.permission_id"
            " where r.code='AI_AGENT'"
        )).scalars().all())
        supervisor = set(db.execute(text(
            "select p.code from shared.app_role_permission rp"
            " join shared.app_role r on r.id=rp.role_id"
            " join shared.app_permission p on p.id=rp.permission_id"
            " where r.code='AI_SUPERVISOR' and p.code like 'ai:%'"
        )).scalars().all())
        cs = set(db.execute(text(
            "select p.code from shared.app_role_permission rp"
            " join shared.app_role r on r.id=rp.role_id"
            " join shared.app_permission p on p.id=rp.permission_id"
            " where r.code='CS_SUPERVISOR' and p.code like 'ai:%'"
        )).scalars().all())
    assert {"AI_AGENT", "AI_SUPERVISOR"} <= roles
    # 四期：坐席追加 tool:read（只读工具），写工具只给主管
    assert agent == {"ai:chat:read", "ai:chat:write", "ai:handoff:read", "ai:handoff:write",
                     "tool:read"}
    # supervisor 这一条只统计 ai:* （查询里带了 like 'ai:%'），tool:* 单独断言
    assert supervisor == {"ai:chat:read", "ai:chat:write", "ai:handoff:read", "ai:handoff:write",
                          "ai:trace:read"}
    assert cs == {"ai:handoff:read"}
    with SessionLocal() as db:
        supervisor_tools = set(db.execute(text(
            "select p.code from shared.app_role_permission rp"
            " join shared.app_role r on r.id=rp.role_id"
            " join shared.app_permission p on p.id=rp.permission_id"
            " where r.code='AI_SUPERVISOR' and p.code like 'tool:%'"
        )).scalars().all())
    assert supervisor_tools == {"tool:read", "tool:write:order", "tool:write:aftersales"}


def test_phone_tail_check_rejects_non_digits():
    definition = _scalar("select pg_get_constraintdef(oid) from pg_constraint where conname='assistant_identity_phone_ck'")
    assert "0-9" in definition
