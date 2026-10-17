"""三期 RAG 编排：plan → execute ⇄ replan → finalize（手写编排循环，不引图框架）。

边界（design 决策 3）：
- 计划 ≤2 步；最大 4 步；最多 1 次 replan；总超时 30s。
- 意图规则词表优先，未命中才调 LLM planner（保护首 token）。
- 检索只调二期 `knowledge_retrieval.search`，不重复实现。
- 引用只由服务端从 `hits` 生成；无命中不调生成模型。
- 护栏：读 `knowledge.rule` 中 escalation 的 `triggers` 词表匹配。
- 图的 finalize 只产出"决策 + 引用 + 提示词"，token 流由路由层消费。
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.models.generated import Rule
from app.services import action as action_service
from app.services import assistant_handoff, knowledge_retrieval, ontology, tool_registry
from app.services.tool_registry import ToolSpec, TOOLS

logger = logging.getLogger(__name__)

MAX_STEPS = 4
MAX_PLAN_STEPS = 2
MAX_REPLANS = 1
TOTAL_TIMEOUT_SECONDS = 30
TOP_K = 5

INTENTS = ("KNOWLEDGE", "REALTIME_FACT", "IDENTITY_REQUEST", "HUMAN_REQUEST")

HUMAN_WORDS = ("转人工", "人工客服", "真人", "找客服", "叫客服")
REALTIME_WORDS = ("到哪了", "到哪儿", "几天能到", "还有多少库存", "现在什么状态", "实时")
IDENTITY_WORDS = ("我的订单", "退款进度", "物流", "快递", "发票", "绑定", "我的设备")
IDENTITY_REQUEST_TEXT = "需要先核验身份：请提供订单号与下单手机号后四位。"
ACTION_PENDING_TEXT = "请确认下面的操作，我才会真正提交；未确认前不会改动订单。"
ACTION_FORBIDDEN_TEXT = "这类操作需要人工客服协助，我这边不能直接办理，建议转人工处理。"

# escalation 规则的 triggers 是英文标识符，用户提问是中文——必须配中文别名表才可能命中。
# 真源：knowledge_raw/13_结构化规则/escalation_aliases.yaml（业务可维护）；
# 下面是文件缺失时的内置回退，保证护栏不会因文件问题整体失效。
ALIAS_FILE = Path(__file__).resolve().parents[2] / "knowledge_raw" / "13_结构化规则" / "escalation_aliases.yaml"

BUILTIN_ALIASES: dict[str, tuple[str, ...]] = {
    "person_trapped": ("被困", "关在里面", "出不去", "门打不开", "锁死", "反锁出不来"),
    "fire": ("着火", "起火", "火灾"),
    "medical_emergency": ("急救", "受伤", "晕倒", "昏迷"),
    "smoke": ("冒烟", "烟雾"),
    "sparks": ("火花", "打火"),
    "electric_shock": ("触电", "电到", "漏电", "麻手"),
    "battery_fire": ("电池起火", "电池着火"),
    "water_near_energized_equipment": ("进水", "水浸", "泡水", "漏水"),
    "abnormal_heat_without_smoke": ("发热", "发烫"),
    "burnt_smell_without_visible_fire": ("焦味", "烧焦"),
    "battery_swelling": ("鼓包", "膨胀", "鼓起来", "变形"),
    "account_takeover": ("账号被盗", "被盗", "被盗号", "异地登录", "不是我登录"),
    "unknown_admin": ("陌生管理员", "陌生账号"),
    "credential_change": ("凭证变更", "改密码"),
    "unknown_camera_access": ("陌生访问", "陌生人访问", "陌生人看", "被陌生人看", "被偷看", "偷窥", "别人能看"),
    "unexpected_sharing": ("异常分享",),
    "batch_device_failure": ("批量故障", "批量坏"),
    "cloud_region_outage": ("云服务故障", "云端不可用"),
    "core_function_unavailable_with_workaround": ("功能不可用",),
    "remote_unlock": ("远程开锁", "远程开门"),
}

_alias_cache: dict[str, tuple[str, ...]] | None = None


def load_escalation_aliases() -> dict[str, tuple[str, ...]]:
    """优先读数据文件；缺失或损坏时回退内置字典并告警。"""
    global _alias_cache
    if _alias_cache is not None:
        return _alias_cache
    try:
        import yaml

        data = yaml.safe_load(ALIAS_FILE.read_text(encoding="utf-8")) or {}
        loaded = {
            str(key): tuple(str(item) for item in (value or []))
            for key, value in data.items()
        }
        if loaded:
            _alias_cache = loaded
            return loaded
    except Exception as exc:  # noqa: BLE001 - 文件问题不能拖垮护栏
        logger.warning("别名表加载失败，回退内置字典：%s", exc)
    _alias_cache = BUILTIN_ALIASES
    return _alias_cache


def reset_alias_cache() -> None:
    global _alias_cache
    _alias_cache = None


PRODUCT_RE = re.compile(r"\bQA?-[A-Z0-9]{2,}(?:-[A-Z0-9]+)*\b|\bQ[A-Z]-[A-Z0-9]{3,}\b")
RULE_RE = re.compile(r"\bKB-RULE-[A-Z0-9-]+\b")

INSTRUCTION_PREFIX = "以下为一般口径，具体以你的订单为准。\n"
CLARIFY_TEXT = "为了更准确地回答，能补充一下具体型号或场景吗？例如：门锁 / 摄像头 / 扫地机。"
REFUSE_TEXT = "这个问题我在知识库里没有找到可靠依据，建议转人工确认，避免给你错误信息。"
SCOPE_TEXT = "关于实时状态（物流位置、库存数量、账户余额），我这里只能说明判定口径，具体数值需要核验身份后由人工确认。"
HANDOFF_TEXT = "已为你转接人工客服，请稍候。"


@dataclass
class State:
    question: str
    intent: str | None = None
    plan: list[str] = field(default_factory=list)
    observations: list[dict] = field(default_factory=list)
    hits: list[dict] = field(default_factory=list)
    replans: int = 0
    steps: int = 0
    decision: str = "ANSWER"          # ANSWER | CLARIFY | REFUSE | HANDOFF | SCOPE
    citations: list[dict] = field(default_factory=list)
    guard_hints: list[str] = field(default_factory=list)
    prompt_messages: list[dict] = field(default_factory=list)
    conversation_id: int | None = None                   # 四期：核验门禁需要会话上下文
    tool_stream: bool = False                            # 四期：工具分支交给流式执行
    pending_action: dict | None = None                   # 四期：待确认动作（写工具）
    facts: list[dict] = field(default_factory=list)      # 四期：工具返回的事实块
    tool_calls: list[dict] = field(default_factory=list) # 四期：工具调用留痕（落 tool_call 表）
    entities: list[dict] = field(default_factory=list)   # 四期：本体归一结果
    boost_entities: list[str] = field(default_factory=list)  # 四期：产品名宽松命中（仅排序）
    match_method: str | None = None                       # exact | fuzzy
    product_scope: str | None = None                     # 四期：映射到二期已有过滤键
    expanded: bool = False                               # 四期：是否已做过一跳扩展
    degraded: bool = False
    started: float = field(default_factory=time.monotonic)

    def elapsed(self) -> float:
        return time.monotonic() - self.started


# 一期种子单号是 QY…，测试用例里用 SO…；两种都要认，否则"查订单/取消订单"进不了工具分支
ORDER_NO_RE = re.compile(r"\b(?:SO|QY)[0-9]{6,}\b")
PRODUCT_WORDS = ("型号", "价格", "多少钱", "有货", "在售", "参数", "规格")
# 只在"我的单据"这种表述下进工具分支；不加泛词"订单"，否则政策类问题也会白付一次模型往返
MY_ORDER_WORDS = ("我订单", "我的订单", "订单里", "我的单", "我买的")
MODEL_CODE_RE = re.compile(r"\bQ[LCHR]-[A-Z0-9]{2,}\b")


def classify_rule(question: str) -> str | None:
    text = question or ""
    if any(word in text for word in HUMAN_WORDS):
        return "HUMAN_REQUEST"
    # 四期：带订单号或型号的问题确定性进工具分支（不额外调模型）
    if ORDER_NO_RE.search(text) or MODEL_CODE_RE.search(text):
        return "REALTIME_FACT"
    if any(word in text for word in PRODUCT_WORDS):
        return "REALTIME_FACT"
    if any(word in text for word in MY_ORDER_WORDS):
        return "IDENTITY_REQUEST"
    if any(word in text for word in REALTIME_WORDS):
        return "REALTIME_FACT"
    if any(word in text for word in IDENTITY_WORDS):
        return "IDENTITY_REQUEST"
    return None


def classify(question: str) -> tuple[str, bool]:
    """返回 (intent, 是否规则命中)。

    规则未命中时**默认不调模型**：三期只有"检索"一条可执行路径，让模型判意图
    只会给每个普通问题加 3–5s 首字延迟。需要时用 ASSISTANT_USE_LLM_PLANNER 打开。
    """
    rule = classify_rule(question)
    if rule:
        return rule, True
    if not settings.assistant_use_llm_planner:
        return "KNOWLEDGE", False
    try:
        from app.integrations import llm

        result = llm.complete([
            {"role": "system", "content": "只输出一个词：KNOWLEDGE / REALTIME_FACT / IDENTITY_REQUEST / HUMAN_REQUEST"},
            {"role": "user", "content": question},
        ])
        text = (result.get("text") or "").strip().upper()
        for intent in INTENTS:
            if intent in text:
                return intent, False
    except Exception:  # noqa: BLE001 - 规划失败退化为知识问答
        pass
    return "KNOWLEDGE", False


def rewrite_query(question: str) -> str:
    """确定性改写：去掉疑问词与标点，保留名词性片段（零命中重试用）。"""
    cleaned = re.sub(r"[？?！!。，,、\s]", "", question or "")
    for word in ("怎么办", "怎么", "如何", "能不能", "可以", "吗", "呢", "请问"):
        cleaned = cleaned.replace(word, "")
    return cleaned[:30] or (question or "")[:30]


def search_knowledge(db: Session, state: dict, args: dict) -> dict:
    """兼容既有调用：直接走注册表里的实现，避免工具定义出现第二份。"""
    return TOOLS["search_knowledge"].run(db, state, args)


def plan(state: State) -> State:
    intent, _rule = classify(state.question)
    state.intent = intent
    if intent == "HUMAN_REQUEST":
        state.decision = "HANDOFF"
        state.plan = ["handoff"]
    elif intent in ("IDENTITY_REQUEST", "REALTIME_FACT"):
        # 四期：事实类问题进工具分支；工具没结果时回退知识检索
        state.plan = ["tool"]
        state.decision = "ANSWER"
    else:
        state.plan = ["search", "answer"]
        state.decision = "ANSWER"
    state.plan = state.plan[:MAX_PLAN_STEPS]
    return state


def normalize(db: Session, state: State) -> State:
    """检索前实体归一：把问题映射到本体实体，并转成二期已支持的过滤键。

    零命中时不带任何过滤，检索行为与三期完全一致。
    """
    try:
        result = ontology.normalize_question(db, state.question)
    except Exception as exc:  # noqa: BLE001 - 本体不可用不能拖垮问答
        logger.warning("本体归一失败，退化为原样检索：%s", exc)
        result = {"entities": [], "product_scope": None}
    state.entities = result.get("entities") or []
    state.product_scope = result.get("product_scope")
    state.boost_entities = [item["code"] for item in (result.get("boost_entities") or [])]
    state.match_method = result.get("method")
    # 归一不是一次检索，不写 retrieval_trace；结果随消息元数据留痕
    return state


def _filters(db: Session, state: State) -> dict | None:
    """只在二期文档对该产品范围确有覆盖时才加过滤。

    实测二期 152 篇文档的 product_scope 全为 NULL，无条件过滤会把召回打成 0；
    因此这里做覆盖守卫，未覆盖时检索行为与三期完全一致。
    """
    if not state.product_scope:
        return None
    try:
        covered = ontology.product_scope_covered(db, state.product_scope)
    except Exception as exc:  # noqa: BLE001 - 守卫失败按不过滤处理
        logger.warning("产品范围覆盖检查失败：%s", exc)
        return None
    return {"product_scope": state.product_scope} if covered else None


def _search(db: Session, state: State, query: str, *, actor: dict | None,
            identity_level: str, extra_filters: dict | None = None) -> dict:
    """带过滤检索；若过滤把召回打成 0，退回不带过滤再试一次（记录留痕）。"""
    filters = extra_filters if extra_filters is not None else _filters(db, state)
    observation = TOOLS["search_knowledge"].run(
        db, {"question": state.question},
        {"query": query, "actor": actor, "identity_level": identity_level, "filters": filters},
    )
    if filters and not observation["hits"]:
        state.observations.append({"tool": "filter_fallback", "ok": True, "query": query,
                                   "dropped_filters": filters})
        observation = TOOLS["search_knowledge"].run(
            db, {"question": state.question},
            {"query": query, "actor": actor, "identity_level": identity_level, "filters": None},
        )
    return observation


def execute(db: Session, state: State, *, actor: dict | None, identity_level: str = "public") -> State:
    if state.decision != "ANSWER":
        return state
    state.steps += 1
    observation = _search(db, state, state.question, actor=actor, identity_level=identity_level)
    state.observations.append({"tool": "search_knowledge", "ok": True, **observation})
    state.hits = observation["hits"]
    return state


def replan(db: Session, state: State, *, actor: dict | None, identity_level: str = "public") -> State:
    """零命中时改写查询重试一次（唯一的重规划规则）。"""
    if state.decision != "ANSWER" or state.hits or state.replans >= MAX_REPLANS or state.steps >= MAX_STEPS:
        return state
    state.replans += 1
    state.steps += 1
    rewritten = rewrite_query(state.question)
    state.observations.append({"tool": "search_knowledge", "query": rewritten, "rewrite": True})
    observation = _search(db, state, rewritten, actor=actor, identity_level=identity_level)
    state.observations[-1].update({"ok": True, **observation})
    state.hits = observation["hits"]
    return state


TOOL_SYSTEM_PROMPT = (
    "你是栖云智家客服助手。需要订单、物流、支付、售后、发票或商品事实时，调用相应工具；"
    "只查知识政策时用 search_knowledge。不要重复调用同一个工具，最多 3 次。"
    "用户没有给出订单号时不要调用订单类工具。"
    "工具返回失败或查不到时，只说明未查到并请用户核对后重试，"
    "不得推测失败原因，不得描述订单号格式、前缀或任何业务规则。"
    "只要用户给出了订单号且会话已通过核验，就必须调用订单类工具去查，"
    "不要重复索要订单号或手机号后四位。"
    "用户提到自己的订单但没给订单号时，先调 query_my_orders 列出并按商品名过滤，"
    "不要直接索要订单号。"
    "回答涉及退货、保修、时效、费用等政策时，必须同时调 search_knowledge 取依据，"
    "不要凭印象回答政策。"
)


def _call_parts(call: dict) -> tuple[str | None, str | None, str | None]:
    """兼容两种形状：流式事件是扁平的，complete() 是 OpenAI 嵌套的。"""
    function = call.get("function") or {}
    name = function.get("name") or call.get("name")
    raw = function.get("arguments")
    if raw is None:
        raw = call.get("arguments")
    return call.get("id"), name, raw


def _assistant_tool_message(calls: list[dict]) -> dict:
    shaped = []
    for call in calls:
        call_id, name, raw = _call_parts(call)
        shaped.append({"id": call_id, "type": "function",
                       "function": {"name": name, "arguments": raw or "{}"}})
    return {"role": "assistant", "content": "", "tool_calls": shaped}


def _round_stream(messages: list[dict], schemas: list[dict]) -> tuple[str, list[dict], str | None]:
    """跑一轮带 tools 的流式调用：累积 tool_calls，返回 (叙述文本, 工具调用, finish_reason)。"""
    from app.integrations import llm

    content: list[str] = []
    calls: list[dict] = []
    finish: str | None = None
    for kind, payload in llm.stream_events(messages, tools=schemas):
        if kind == "content":
            content.append(payload.get("text") or "")
        elif kind == "tool_call":
            calls.append(payload)
        elif kind == "finish":
            finish = payload.get("reason")
    return "".join(content), calls, finish


def stream_tool_answer(db: Session, state: State, *, actor: dict | None, identity_level: str,
                       history: list[dict], permissions: set[str] | None = None,
                       conversation: object | None = None, message_id: int | None = None,
                       max_calls: int = 3):
    """单段流式工具分支：产出 ("text", 文本) 与 ("tool", 状态) 两类事件。

    B2 语义：带 tools 的轮次里叙述先缓冲，工具事件先发，缓冲叙述随后下发；
    纯文本轮次则边收边发。
    """
    permissions = permissions or set()
    if (actor or {}).get("party") == "STAFF":
        allow_write = bool(permissions & set(action_service.WRITE_TOOL_PERMISSION.values()))
    else:
        # 客户侧不持有 tool:* 权限码，写能力由开关 + 核验门禁控制
        allow_write = settings.assistant_customer_write_enabled
    schemas = tool_registry.llm_tools(include_write=allow_write)
    messages = [{"role": "system", "content": TOOL_SYSTEM_PROMPT}, *history,
                {"role": "user", "content": state.question}]
    calls_used = 0
    rounds = 0
    while rounds <= max_calls:
        rounds += 1
        text, tool_calls, _finish = _round_stream(messages, schemas)
        if not tool_calls:
            if text:
                yield ("text", text)
            return
        pending_messages: list[dict] = []
        for call in tool_calls:
            if calls_used >= max_calls:
                break
            calls_used += 1
            call_id, name, raw_arguments = _call_parts(call)
            spec = TOOLS.get(name)
            started = time.monotonic()
            if spec is None or (not spec.read_only and not allow_write):
                state.tool_calls.append({"tool_name": name or "unknown", "args": {},
                                         "status": "REJECTED", "error_code": "TOOL_NOT_ALLOWED",
                                         "latency_ms": 0})
                yield ("tool", {"name": name, "status": "failed", "latency_ms": 0})
                pending_messages.append({"role": "tool", "tool_call_id": call_id,
                                         "content": json.dumps({"error": "TOOL_NOT_ALLOWED"},
                                                               ensure_ascii=False)})
                continue
            try:
                args = tool_registry.validate_args(spec, tool_registry.parse_arguments(
                    raw_arguments))
            except Exception as exc:  # noqa: BLE001
                state.tool_calls.append({"tool_name": spec.name, "args": {}, "status": "REJECTED",
                                         "error_code": "VALIDATION_FAILED", "latency_ms": 0})
                yield ("tool", {"name": spec.name, "status": "failed", "latency_ms": 0})
                pending_messages.append({"role": "tool", "tool_call_id": call_id,
                                         "content": json.dumps({"error": "VALIDATION_FAILED",
                                                                "message": str(exc)},
                                                               ensure_ascii=False)})
                continue
            if spec.requires_identity:
                verified = assistant_handoff.active_verification(db, state.conversation_id)                     if state.conversation_id else None
                if verified is None or verified.order_no != args.get("order_no"):
                    state.decision = "IDENTITY_REQUEST"
                    state.tool_calls.append({"tool_name": spec.name, "args": args,
                                             "status": "REJECTED",
                                             "error_code": "IDENTITY_REQUIRED", "latency_ms": 0})
                    yield ("tool", {"name": spec.name, "status": "failed", "latency_ms": 0})
                    yield ("text", IDENTITY_REQUEST_TEXT)
                    return
            if not spec.read_only:
                needed = action_service.WRITE_TOOL_PERMISSION.get(spec.name)
                party = (actor or {}).get("party")
                if party == "STAFF":
                    allowed = not needed or needed in permissions
                else:
                    # 客户侧不持有 tool:* 权限码：按"是否已核验 + 租户开关"放行，
                    # 写操作本身仍受二次确认、幂等与审计约束（design 业1=B 白名单灰度）
                    allowed = settings.assistant_customer_write_enabled
                if not allowed:
                    state.tool_calls.append({"tool_name": spec.name, "args": args,
                                             "status": "REJECTED", "error_code": "PERM_FORBIDDEN",
                                             "latency_ms": 0})
                    yield ("tool", {"name": spec.name, "status": "failed", "latency_ms": 0})
                    yield ("text", ACTION_FORBIDDEN_TEXT)
                    return
                if conversation is None or message_id is None:
                    state.tool_calls.append({"tool_name": spec.name, "args": args,
                                             "status": "REJECTED", "error_code": "NO_CONTEXT",
                                             "latency_ms": 0})
                    return
                try:
                    snapshot = None
                    try:
                        found = tool_registry.resolve_order(db, actor or {}, args.get("order_no"))
                        snapshot = {"status": found.status, "order_no": found.order_no}
                    except Exception:  # noqa: BLE001
                        snapshot = None
                    state.pending_action = action_service.propose(
                        db, actor or {}, conversation=conversation, message_id=message_id,
                        tool_name=spec.name, args=args, facts=snapshot)
                except AppError as exc:
                    state.tool_calls.append({"tool_name": spec.name, "args": args,
                                             "status": "REJECTED", "error_code": exc.code,
                                             "latency_ms": 0})
                    state.facts.append({"tool": spec.name, "ok": False, "error_code": exc.code,
                                        "message": exc.message})
                    yield ("tool", {"name": spec.name, "status": "failed", "latency_ms": 0})
                    return
                state.tool_calls.append({"tool_name": spec.name, "args": args, "status": "OK",
                                         "error_code": None, "latency_ms": 0})
                state.decision = "ACTION_PROPOSED"
                yield ("tool", {"name": spec.name, "status": "ok", "latency_ms": 0})
                if text:
                    yield ("text", text)
                yield ("text", ACTION_PENDING_TEXT)
                return
            try:
                result = spec.run(db, {"question": state.question, "actor": actor,
                                       "identity_level": identity_level,
                                       "conversation_id": state.conversation_id}, args)
            except Exception as exc:  # noqa: BLE001
                code = str(getattr(exc, "code", "TOOL_FAILED"))
                latency = int((time.monotonic() - started) * 1000)
                state.tool_calls.append({"tool_name": spec.name, "args": args,
                                         "status": "FAILED", "error_code": code,
                                         "latency_ms": latency})
                state.facts.append({"tool": spec.name, "ok": False, "error_code": code,
                                    "message": getattr(exc, "message", str(exc))})
                yield ("tool", {"name": spec.name, "status": "failed", "latency_ms": latency})
                pending_messages.append({"role": "tool", "tool_call_id": call_id,
                                         "content": json.dumps({"error": code}, ensure_ascii=False)})
                continue
            latency = int((time.monotonic() - started) * 1000)
            state.tool_calls.append({"tool_name": spec.name, "args": args, "status": "OK",
                                     "error_code": None, "latency_ms": latency})
            payload = result.get("facts")
            if payload is None and result.get("hits") is not None:
                # 知识检索没有 facts 结构：把命中压成可直接引用的事实块，并并入 citations 来源
                payload = {"hits": [{"document_id": hit.get("document_id"),
                                     "title_path": hit.get("title_path"),
                                     "snippet": (hit.get("snippet") or "")[:240]}
                                    for hit in (result.get("hits") or [])[:5]]}
                state.hits = _merge_hits(state.hits, result.get("hits") or [])
            state.facts.append({"tool": spec.name, "ok": True,
                                "facts": payload, "note": result.get("note")})
            yield ("tool", {"name": spec.name, "status": "ok", "latency_ms": latency})
            pending_messages.append({"role": "tool", "tool_call_id": call_id,
                                     "content": json.dumps(payload, ensure_ascii=False)})
        # 缓冲的叙述在工具事件之后下发
        if text:
            yield ("text", text)
        messages.append(_assistant_tool_message(tool_calls))
        messages.extend(pending_messages)
        if state.tool_calls and all(call["status"] == "REJECTED" for call in state.tool_calls):
            return
    # 轮次用尽：不带工具收个尾
    text, _calls, _finish = _round_stream(messages, [])
    if text:
        yield ("text", text)


def tool_loop(db: Session, state: State, *, actor: dict | None, identity_level: str,
              history: list[dict], max_calls: int = 3, permissions: set[str] | None = None,
              conversation: object | None = None, message_id: int | None = None) -> State:
    """非流式用法：把流式实现跑干（测试与内部调用共用同一套逻辑）。"""
    for _kind, _payload in stream_tool_answer(
            db, state, actor=actor, identity_level=identity_level, history=history,
            permissions=permissions, conversation=conversation, message_id=message_id,
            max_calls=max_calls):
        pass
    return state


def rank_by_ontology(db: Session, state: State) -> State:
    """本体参与排序：命中切片若挂到归一实体（或邻接实体），前置并保持其余原序。

    这是"本体影响检索"的兜底手段——二期 product_scope 未回填时，过滤条件用不上，
    但切片映射（chunk_entity）是四期自己可控的，可以稳定地改变排序。
    """
    if not state.hits or (not state.entities and not state.boost_entities):
        return state
    entity_codes = {item["code"] for item in state.entities} | set(state.boost_entities)
    try:
        boosted, rest = [], []
        for hit in state.hits:
            codes = ontology.chunk_entity_codes(db, hit.get("document_id"), hit.get("version"),
                                                hit.get("chunk_ord"))
            (boosted if codes & entity_codes else rest).append(hit)
    except Exception as exc:  # noqa: BLE001 - 排序失败不影响召回
        logger.warning("本体排序失败：%s", exc)
        return state
    if boosted and rest:
        state.hits = [*boosted, *rest]
        state.observations.append({"tool": "ontology_rank", "ok": True,
                                   "boosted": len(boosted), "rest": len(rest)})
    return state


def _merge_hits(first: list[dict], second: list[dict]) -> list[dict]:
    """按 (document_id, version, chunk_ord) 去重，首个来源优先级更高，重编 rank 由调用方负责。"""
    seen: set[tuple] = set()
    merged: list[dict] = []
    for hit in [*first, *second]:
        key = (hit.get("document_id"), hit.get("version"), hit.get("chunk_ord"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(hit)
    return merged


def expand(db: Session, state: State, *, actor: dict | None, identity_level: str = "public") -> State:
    """检索后一跳扩展：借邻接实体的产品范围再检索一次，hits 合并去重。

    只有"归一命中了实体、还有剩余步数、且邻接存在其它产品范围"时才动，
    否则完全保持三期行为。
    """
    if state.decision != "ANSWER" or state.expanded or state.steps >= MAX_STEPS:
        return state
    if not state.product_scope or not state.entities:
        return state
    state.expanded = True
    neighbor_scopes: list[str] = []
    try:
        for entity in state.entities:
            node = ontology.graph(db, int(entity["id"]), depth=1)
            for item in node["nodes"]:
                code = item["entity"]["code"]
                if item["entity"]["kind"] == "product" and code != state.product_scope:
                    if code not in neighbor_scopes:
                        neighbor_scopes.append(code)
    except Exception as exc:  # noqa: BLE001 - 扩展失败按无扩展处理
        logger.warning("本体邻接查询失败，跳过扩展：%s", exc)
        return state
    if not neighbor_scopes:
        return state
    state.steps += 1
    observation = _search(db, state, state.question, actor=actor,
                          identity_level=identity_level,
                          extra_filters={"product_scope": neighbor_scopes[0]})
    before = len(state.hits)
    state.hits = _merge_hits(state.hits, observation["hits"])
    state.observations.append({
        "tool": "ontology_expand", "ok": True, "query": state.question,
        "scope": neighbor_scopes[0], "added": len(state.hits) - before,
        "hits": observation["hits"], "latency_ms": observation.get("latency_ms"),
    })
    return state


STOP_GRAMS = {
    "什么", "怎么", "么办", "如何", "可以", "需要", "是否", "哪些", "多少", "我的",
    "一下", "请问", "问题", "怎样", "为什", "这个", "那个", "还是", "或者", "以及",
}


def _grams(text: str) -> set[str]:
    cleaned = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", text or "")
    grams = {cleaned[index:index + 2] for index in range(len(cleaned) - 1)}
    return {gram for gram in grams if gram not in STOP_GRAMS}


def relevance_of(question: str, hit: dict) -> float:
    """问题与一条命中的关键词重合度（0~1）。"""
    question_grams = _grams(question)
    if not question_grams:
        return 1.0
    target = _grams(f"{hit.get('title_path') or ''} {hit.get('snippet') or ''}")
    return len(question_grams & target) / len(question_grams)


def relevance_ok(question: str, hits: list[dict]) -> bool:
    """任一前 3 条命中足够相关即视为"有命中"；否则整批作废（不给无关引用）。"""
    if not hits:
        return False
    threshold = settings.assistant_relevance_min_ratio
    return any(relevance_of(question, hit) >= threshold for hit in hits[:3])


TAG_KIND_ORDER = {"product": 0, "policy": 1, "part": 2, "fault": 3, "accessory": 4, "action": 5}
MAX_TAGS_PER_CITATION = 8


def _ontology_tags(db: Session, hit: dict) -> list[dict]:
    """四期：优先用本体映射（chunk_entity）生成标签；本体没覆盖时由调用方回退到正则。"""
    try:
        rows = ontology.entities_of_chunk(db, hit.get("document_id"), hit.get("version"),
                                          hit.get("chunk_ord"))
    except Exception as exc:  # noqa: BLE001 - 本体不可用不影响引用生成
        logger.warning("本体标签查询失败：%s", exc)
        return []
    ordered = sorted(rows, key=lambda e: (TAG_KIND_ORDER.get(e.kind, 9), e.code))
    tags: list[dict] = []
    for entity in ordered[:MAX_TAGS_PER_CITATION]:
        if entity.kind == "product":
            tags.append({"type": "product_line", "value": entity.code})
        elif entity.kind == "policy":
            tags.append({"type": "rule_id", "value": entity.code})
        else:
            tags.append({"type": entity.kind, "value": entity.code})
    return tags


def _regex_tags(hit: dict) -> list[dict]:
    snippet = hit.get("snippet") or ""
    tags: list[dict] = []
    match = PRODUCT_RE.search(snippet) or PRODUCT_RE.search(hit.get("title_path") or "")
    if match:
        tags.append({"type": "product_line", "value": match.group(0)})
    for rule_id in RULE_RE.findall(snippet):
        tags.append({"type": "rule_id", "value": rule_id})
    return tags


def build_citations(db: Session, hits: list[dict]) -> list[dict]:
    citations = []
    for rank, hit in enumerate(hits):
        snippet = hit.get("snippet") or ""
        tags = _ontology_tags(db, hit) or _regex_tags(hit)
        citations.append({
            "chunk_id": hit.get("chunk_id"),
            "document_id": hit.get("document_id"),
            "version": hit.get("version"),
            "title_path": hit.get("title_path") or "",
            "line_start": hit.get("line_start"),
            "line_end": hit.get("line_end"),
            "snippet": snippet,
            "rank": rank,
            "entity_tags": tags,
        })
    return citations


def guard_hints(db: Session, question: str) -> list[str]:
    """读 escalation 规则的触发词表做匹配；命中即取该规则 forbid。"""
    rows = db.execute(
        select(Rule).where(Rule.tenant_id == 1, Rule.source_kind == "escalation", Rule.status == "ACTIVE")
    ).scalars().all()
    hints: list[str] = []
    for rule in rows:
        triggers = (rule.condition or {}).get("issue_type") or []
        triggers = triggers if isinstance(triggers, list) else [triggers]
        matched = False
        for trigger in triggers:
            name = str(trigger)
            if name in question or name.replace("_", "") in question:
                matched = True
                break
            if any(alias in question for alias in load_escalation_aliases().get(name, ())):
                matched = True
                break
        if not matched:
            continue
        forbids = rule.forbid if isinstance(rule.forbid, list) else []
        if forbids:
            hints.append("涉及安全风险，请勿自行拆装或远程操作，按安全指引处理。")
    return sorted(set(hints))


FACT_BLOCK_HEADER = (
    "以下为业务系统返回的事实（权威），回答中不要改写其中的金额、单号与时间；"
    "标注为调用失败的条目只说明未查到，不要推测原因或补充业务规则："
)


def _fact_block(state: State) -> str:
    lines = [FACT_BLOCK_HEADER]
    for item in state.facts:
        if item.get("ok"):
            lines.append(f"- {item['tool']}: {json.dumps(item.get('facts'), ensure_ascii=False)}")
        else:
            lines.append(f"- {item['tool']}: 调用失败（{item.get('error_code')}）")
    return "\n".join(lines)


def finalize(db: Session, state: State, *, history: list[dict]) -> State:
    if state.decision in ("IDENTITY_REQUEST", "ACTION_PROPOSED"):
        state.citations = []
        state.prompt_messages = []
        return state
    if state.decision == "ANSWER" and state.facts:
        ok = [item for item in state.facts if item.get("ok")]
        failed = [item for item in state.facts if not item.get("ok")]
        state.citations = []
        if not ok:
            state.decision = "REFUSE"
            state.prompt_messages = []
            return state
        note = ""
        if failed:
            note = "；部分查询未成功，已按已拿到的结果回答"
        # 工具分支里如果查过知识，也要给引用（沿用"引用只由服务端生成"的硬约束）
        if state.hits:
            state.citations = build_citations(db, state.hits)
        state.prompt_messages = [
            {"role": "system", "content": (
                "你是栖云智家客服助手。只依据下方事实与知识作答，不编造；"
                "不重复抄写金额与单号，用自然语言概括。回答不超过 200 字。\n\n" + _fact_block(state)
            )},
            *history,
            {"role": "user", "content": state.question + note},
        ]
        return state
    if state.elapsed() > TOTAL_TIMEOUT_SECONDS:
        state.degraded = True
        state.decision = "REFUSE"
    if state.decision == "ANSWER" and state.hits and not relevance_ok(state.question, state.hits):
        state.observations.append({"tool": "relevance_gate", "ok": False,
                                   "ratio": max(relevance_of(state.question, hit) for hit in state.hits[:3])})
        state.hits = []
    if state.decision == "ANSWER":
        if not state.hits:
            state.decision = "CLARIFY" if len(state.question) < 12 else "REFUSE"
        else:
            state.citations = build_citations(db, state.hits)
            state.guard_hints = guard_hints(db, state.question)
            context = "\n\n".join(
                f"[{hit['document_id']} v{hit['version']}] {hit['title_path']}\n{hit['snippet']}"
                for hit in state.hits
            )
            prefix = INSTRUCTION_PREFIX if state.guard_hints else ""
            guard = ("\n".join(state.guard_hints) + "\n") if state.guard_hints else ""
            state.prompt_messages = [
                {"role": "system", "content": (
                    "你是栖云智家客服助手。只依据下方知识作答，不编造参数/时限/金额；"
                    "不确定就说明并建议转人工。回答不超过 300 字。"
                    "不要向用户展示内部规则编号（ESC-/WARRANTY-/SYM-/QUALITY- 等开头），"
                    "需要指代时用业务说法，例如“升级到热异常处理流程”。\n\n" + context
                )},
                *history,
                {"role": "user", "content": prefix + guard + state.question},
            ]
        return state
    state.prompt_messages = state.prompt_messages or []
    state.citations = []
    return state


def run(db: Session, question: str, *, actor: dict | None, history: list[dict],
        identity_level: str = "public", conversation_id: int | None = None,
        permissions: set[str] | None = None, conversation: object | None = None,
        message_id: int | None = None, defer_tools: bool = False) -> State:
    """跑一遍编排；返回最终 state（decision/citations/prompt_messages）。

    defer_tools=True 时把工具分支交给调用方的流式实现（SSE 路由用）。
    """
    state = State(question=question, conversation_id=conversation_id)
    normalize(db, state)
    plan(state)
    if state.decision == "ANSWER" and state.plan and state.plan[0] == "tool":
        if defer_tools:
            state.tool_stream = True
            return state
        tool_loop(db, state, actor=actor, identity_level=identity_level, history=history,
                  permissions=permissions, conversation=conversation, message_id=message_id)
        if state.decision in ("IDENTITY_REQUEST", "ACTION_PROPOSED") or state.facts:
            return finalize(db, state, history=history)
        # 工具没给出事实：回退到知识检索，行为与三期一致
    while state.steps < MAX_STEPS and state.decision == "ANSWER" and not state.hits:
        execute(db, state, actor=actor, identity_level=identity_level)
        if state.hits:
            break
        replan(db, state, actor=actor, identity_level=identity_level)
        if not state.hits or state.replans >= MAX_REPLANS:
            break
    if state.hits:
        rank_by_ontology(db, state)
        expand(db, state, actor=actor, identity_level=identity_level)
    return finalize(db, state, history=history)


def fixed_answer(state: State) -> str:
    return {
        "HANDOFF": HANDOFF_TEXT,
        "SCOPE": SCOPE_TEXT,
        "IDENTITY_REQUEST": IDENTITY_REQUEST_TEXT,
        "ACTION_PROPOSED": ACTION_PENDING_TEXT,
        "ACTION_FORBIDDEN": ACTION_FORBIDDEN_TEXT,
        "CLARIFY": CLARIFY_TEXT,
        "REFUSE": REFUSE_TEXT,
        "ANSWER": "",
    }[state.decision]
