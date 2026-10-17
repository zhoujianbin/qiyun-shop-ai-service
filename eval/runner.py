"""L1 评测执行器：确定性替身 + 桩化工具结果，只测服务端链路。

明确边界：这里测的不是"模型选对率"，而是"拿到 tool_call 之后服务端做得对不对"。
"""
from __future__ import annotations

import re
from contextlib import ExitStack
from unittest import mock

from app.core.db import SessionLocal
from app.core.errors import NotFound
from app.integrations import llm
from app.models.generated import AppUser, CustomerProfile
from app.models.generated import Conversation
from app.services import (
    assistant_conversation as conversation_service,
    assistant_graph, assistant_handoff, knowledge_retrieval, tool_registry,
)
from sqlalchemy import select, text


def _actor(db) -> dict:
    user = db.execute(select(AppUser).where(AppUser.username == "buyer_zhang")).scalar_one_or_none()
    if user is None:
        return {"id": 1, "party": "CUSTOMER", "customer_id": 1}
    profile = db.execute(select(CustomerProfile).where(
        CustomerProfile.user_id == user.id)).scalar_one_or_none()
    return {"id": user.id, "party": "CUSTOMER",
            "customer_id": profile.id if profile is not None else user.id}


def _fake_hit(question: str) -> dict:
    return {"chunk_id": 1, "document_id": "EVAL-DOC-001", "version": 1,
            "title_path": "评测桩文档", "line_start": 1, "line_end": 2,
            "snippet": question, "chunk_ord": 1}


def run_l1(case: dict) -> dict:
    """执行一条 L1 用例，返回结构化结果（不含断言结论）。"""
    setup = case.get("setup") or {}
    scripted = list(case.get("attempt_tool") or case.get("must_call_tool") or [])
    forbidden = list(case.get("must_not_call_tool") or [])
    if not scripted and forbidden:
        scripted = [forbidden[0]]
    def args_for(name: str) -> dict:
        spec = tool_registry.TOOLS.get(name)
        allowed = (spec.input_schema.get("properties") or {}) if spec is not None else {}
        pool = {"order_no": setup.get("order_no") or "SO20260101001234",
                "reason": "用户要求取消", "keyword": "门锁", "model_code": "QL-L3P",
                "query": case["question"], "top_k": 5,
                "type": "RETURN_REFUND", "reason_code": "NO_LONGER_NEEDED",
                "quantity": 1, "description": "评测用例"}
        return {key: value for key, value in pool.items() if key in allowed}

    calls = [{"name": name, "arguments": args_for(name)} for name in scripted]
    expected_error = {name for name in forbidden}

    def stub_run(name: str, facts: dict):
        def _run(db, state, args):
            if name in expected_error:
                raise NotFound("没有找到该订单")
            return {"facts": facts}
        return _run

    provider = llm.FakeProvider()
    provider.script(calls)
    results = {"id": case["id"], "category": case["category"], "question": case["question"],
               "decision": None, "tool_calls": [], "citations": 0, "entities": [],
               "prompt": "", "error": None}
    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(llm, "_provider", provider))
        stack.enter_context(mock.patch.object(llm, "get_provider", lambda: provider))
        hits = [] if setup.get("retrieval") == "empty" or case.get("retrieval") == "empty"             else [_fake_hit(case["question"])]
        stack.enter_context(mock.patch.object(
            knowledge_retrieval, "search",
            lambda db, query, **kw: {"hits": hits,
                                     "debug": {"latency_ms": 1, "vector_score": {},
                                               "text_score": {}, "fused_score": {},
                                               "candidates": len(hits)}}))
        for name in set(scripted):
            spec = tool_registry.TOOLS.get(name)
            if spec is not None and spec.run is not None:
                stack.enter_context(mock.patch.object(
                    spec, "run", stub_run(name, {"order_no": setup.get("order_no"),
                                                 "status": "SHIPPED", "products": []})))
        if setup.get("identity") == "verified":
            verified = type("V", (), {"order_no": setup.get("order_no"), "status": "VERIFIED",
                                      "expires_at": None})()
            stack.enter_context(mock.patch.object(
                assistant_handoff, "active_verification", lambda db, cid: verified))
        else:
            stack.enter_context(mock.patch.object(
                assistant_handoff, "active_verification", lambda db, cid: None))
        with SessionLocal() as db:
            actor_info = _actor(db)
            permissions = {"tool:read", "tool:write:order", "tool:write:aftersales"}
            conversation = None
            message_id = None
            write_tools = {name for name in scripted
                           if name in tool_registry.TOOLS
                           and not tool_registry.TOOLS[name].read_only}
            created_conversation_id = None
            if write_tools:
                created = conversation_service.create_conversation(db, actor_info)
                created_conversation_id = created["id"]
                placeholder = conversation_service.append_message(
                    db, created["id"], role="ASSISTANT", content="", status="STREAMING")
                conversation = db.get(Conversation, created["id"])
                message_id = placeholder.id
            try:
                state = assistant_graph.run(
                    db, case["question"], actor=actor_info, history=[],
                    identity_level="customer" if setup.get("identity") == "verified" else "public",
                    conversation_id=1, permissions=permissions,
                    conversation=conversation, message_id=message_id)
            except Exception as exc:  # noqa: BLE001 - 用例失败要记下来而不是炸掉整批
                results["error"] = f"{type(exc).__name__}: {exc}"
                return results
            results["decision"] = state.decision
            results["tool_calls"] = [call.get("tool_name") for call in state.tool_calls]
            results["tool_calls_ok"] = [call.get("tool_name") for call in state.tool_calls
                                        if call.get("status") == "OK"]
            results["citations"] = len(state.citations)
            results["entities"] = [item["code"] for item in state.entities]
            results["prompt"] = "\n".join(
                str(message.get("content") or "") for message in (state.prompt_messages or []))
            results["pending_action"] = state.pending_action
            results["fixed_text"] = assistant_graph.fixed_answer(state)
            if state.tool_stream:
                # 流式分支：跑干一遍拿到文本与工具留痕
                text = "".join(payload for kind, payload in assistant_graph.stream_tool_answer(
                    db, state, actor=_actor(db),
                    identity_level="customer" if setup.get("identity") == "verified" else "public",
                    history=[], conversation=None, message_id=None) if kind == "text")
                results["prompt"] = text
            # 评测必须可重放且不污染业务库：本用例建的会话/占位消息/待确认动作全部清掉
            # （action.propose 内部会 commit，所以这里用新会话删除而不是回滚）
            if created_conversation_id is not None:
                _discard_case_rows(created_conversation_id)
    provider.script(None)
    return results


def _discard_case_rows(conversation_id: int) -> None:
    """清理评测用例在业务库留下的副作用（幂等、失败不抛出）。"""
    try:
        with SessionLocal() as db:
            db.execute(text("delete from assistant.pending_action where conversation_id = :c"),
                       {"c": conversation_id})
            db.execute(text("delete from assistant.tool_call where conversation_id = :c"),
                       {"c": conversation_id})
            db.execute(text("delete from assistant.citation where message_id in"
                            " (select id from assistant.message where conversation_id = :c)"),
                       {"c": conversation_id})
            db.execute(text("delete from assistant.message where conversation_id = :c"),
                       {"c": conversation_id})
            db.execute(text("delete from assistant.conversation where id = :c"),
                       {"c": conversation_id})
            db.commit()
    except Exception:  # noqa: BLE001 - 清理失败不应影响评测结论
        pass


def checks_of(case: dict, result: dict) -> dict[str, bool]:
    """把用例断言翻译成布尔结果。"""
    checks: dict[str, bool] = {}
    if result.get("error"):
        return {"无异常": False}
    executed = set(result.get("tool_calls_ok") or [])
    if case.get("must_call_tool"):
        checks["必须调用工具"] = set(case["must_call_tool"]) <= executed
    if case.get("must_not_call_tool"):
        # 允许出现"尝试调用但被拒"的留痕，只要求没有真正执行
        checks["不得执行工具"] = not (set(case["must_not_call_tool"]) & executed)
    if case.get("must_cite"):
        checks["必须带引用"] = result.get("citations", 0) > 0
    if case.get("must_refuse"):
        checks["必须拒答"] = result.get("decision") in ("REFUSE", "CLARIFY")
    if case.get("must_handoff"):
        checks["必须转人工"] = result.get("decision") == "HANDOFF"
    if case.get("must_confirm"):
        checks["必须生成待确认动作"] = bool(result.get("pending_action"))
    if case.get("must_request_identity"):
        checks["必须要求核验"] = result.get("decision") == "IDENTITY_REQUEST"
    if case.get("expected_entities"):
        checks["实体归一"] = set(case["expected_entities"]) <= set(result.get("entities") or [])
    if case.get("forbidden_patterns"):
        text = f"{result.get('prompt') or ''}{result.get('fixed_text') or ''}"
        checks["禁止词"] = not any(re.search(pattern, text)
                                  for pattern in case["forbidden_patterns"])
    return checks
