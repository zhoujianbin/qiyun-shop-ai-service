"""三期 RAG 编排：plan → execute ⇄ replan → finalize（LangGraph，一条件边）。

边界（design 决策 3）：
- 计划 ≤2 步；最大 4 步；最多 1 次 replan；总超时 30s。
- 意图规则词表优先，未命中才调 LLM planner（保护首 token）。
- 检索只调二期 `knowledge_retrieval.search`，不重复实现。
- 引用只由服务端从 `hits` 生成；无命中不调生成模型。
- 护栏：读 `knowledge.rule` 中 escalation 的 `triggers` 词表匹配。
- 图的 finalize 只产出"决策 + 引用 + 提示词"，token 流由路由层消费。
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.generated import Rule
from app.services import knowledge_retrieval

MAX_STEPS = 4
MAX_PLAN_STEPS = 2
MAX_REPLANS = 1
TOTAL_TIMEOUT_SECONDS = 30
TOP_K = 5

INTENTS = ("KNOWLEDGE", "REALTIME_FACT", "IDENTITY_REQUEST", "HUMAN_REQUEST")

HUMAN_WORDS = ("转人工", "人工客服", "真人", "找客服", "叫客服")
REALTIME_WORDS = ("到哪了", "到哪儿", "几天能到", "还有多少库存", "现在什么状态", "实时")
IDENTITY_WORDS = ("我的订单", "退款进度", "物流", "快递", "发票", "绑定", "我的设备")

# escalation 规则的 triggers 是英文标识符，用户提问是中文——必须配中文别名表才可能命中。
# 只覆盖安全红线相关的 trigger，别名取自 knowledge_raw/13_结构化规则/escalation_matrix.yaml 的语义。
ESCALATION_ALIASES: dict[str, tuple[str, ...]] = {
    "person_trapped": ("被困", "关在里面", "出不去", "门打不开"),
    "fire": ("着火", "起火", "火灾"),
    "medical_emergency": ("急救", "受伤", "晕倒", "昏迷"),
    "smoke": ("冒烟", "烟雾"),
    "sparks": ("火花", "打火"),
    "electric_shock": ("触电", "电到"),
    "battery_fire": ("电池起火", "电池着火"),
    "water_near_energized_equipment": ("进水", "水浸", "泡水"),
    "abnormal_heat_without_smoke": ("发热", "发烫"),
    "burnt_smell_without_visible_fire": ("焦味", "烧焦"),
    "battery_swelling": ("鼓包", "膨胀"),
    "account_takeover": ("账号被盗", "被盗"),
    "unknown_admin": ("陌生管理员", "陌生账号"),
    "credential_change": ("凭证变更", "改密码"),
    "unknown_camera_access": ("陌生访问", "被陌生人看"),
    "unexpected_sharing": ("异常分享",),
    "batch_device_failure": ("批量故障", "批量坏"),
    "cloud_region_outage": ("云服务故障", "云端不可用"),
    "core_function_unavailable_with_workaround": ("功能不可用",),
    "remote_unlock": ("远程开锁", "远程开门"),
}

PRODUCT_RE = re.compile(r"\bQA?-[A-Z0-9]{2,}(?:-[A-Z0-9]+)*\b|\bQ[A-Z]-[A-Z0-9]{3,}\b")
RULE_RE = re.compile(r"\bKB-RULE-[A-Z0-9-]+\b")

INSTRUCTION_PREFIX = "以下为一般口径，具体以你的订单为准。\n"
CLARIFY_TEXT = "为了更准确地回答，能补充一下具体型号或场景吗？例如：门锁 / 摄像头 / 扫地机。"
REFUSE_TEXT = "这个问题我在知识库里没有找到可靠依据，建议转人工确认，避免给你错误信息。"
SCOPE_TEXT = "关于实时状态（物流位置、库存数量、账户余额），我这里只能说明判定口径，具体数值需要核验身份后由人工确认。"
HANDOFF_TEXT = "已为你转接人工客服，请稍候。"


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    run: Callable[[Session, dict, dict], dict]
    read_only: bool = True
    requires_identity: bool = False
    scope: str = "knowledge"


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
    degraded: bool = False
    started: float = field(default_factory=time.monotonic)

    def elapsed(self) -> float:
        return time.monotonic() - self.started


def classify_rule(question: str) -> str | None:
    text = question or ""
    if any(word in text for word in HUMAN_WORDS):
        return "HUMAN_REQUEST"
    if any(word in text for word in REALTIME_WORDS):
        return "REALTIME_FACT"
    if any(word in text for word in IDENTITY_WORDS):
        return "IDENTITY_REQUEST"
    return None


def classify(question: str) -> tuple[str, bool]:
    """返回 (intent, 是否规则命中)。未命中才调 LLM。"""
    rule = classify_rule(question)
    if rule:
        return rule, True
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
    result = knowledge_retrieval.search(
        db, args.get("query") or state["question"],
        top_k=args.get("top_k", TOP_K), actor=args.get("actor"), identity_level=args.get("identity_level", "public"),
    )
    return {"hits": result["hits"], "latency_ms": result["debug"]["latency_ms"]}


TOOLS: dict[str, ToolSpec] = {
    "search_knowledge": ToolSpec(
        name="search_knowledge",
        description="在企业知识库中检索与问题相关的切片",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        run=search_knowledge,
        read_only=True,
        requires_identity=False,
        scope="knowledge",
    ),
}


def plan(state: State) -> State:
    intent, _rule = classify(state.question)
    state.intent = intent
    if intent == "HUMAN_REQUEST":
        state.decision = "HANDOFF"
        state.plan = ["handoff"]
    elif intent == "IDENTITY_REQUEST":
        state.plan = ["identity"]
        state.decision = "SCOPE"
    elif intent == "REALTIME_FACT":
        state.plan = ["scope"]
        state.decision = "SCOPE"
    else:
        state.plan = ["search", "answer"]
        state.decision = "ANSWER"
    state.plan = state.plan[:MAX_PLAN_STEPS]
    return state


def execute(db: Session, state: State, *, actor: dict | None, identity_level: str = "public") -> State:
    if state.decision != "ANSWER":
        return state
    state.steps += 1
    observation = TOOLS["search_knowledge"].run(
        db, {"question": state.question}, {"query": state.question, "actor": actor, "identity_level": identity_level}
    )
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
    observation = TOOLS["search_knowledge"].run(
        db, {"question": state.question}, {"query": rewritten, "actor": actor, "identity_level": identity_level}
    )
    state.observations[-1].update({"ok": True, **observation})
    state.hits = observation["hits"]
    return state


def build_citations(hits: list[dict]) -> list[dict]:
    citations = []
    for rank, hit in enumerate(hits):
        snippet = hit.get("snippet") or ""
        tags = []
        if PRODUCT_RE.search(snippet) or PRODUCT_RE.search(hit.get("title_path") or ""):
            match = PRODUCT_RE.search(snippet) or PRODUCT_RE.search(hit.get("title_path") or "")
            tags.append({"type": "product_line", "value": match.group(0)})
        for rule_id in RULE_RE.findall(snippet):
            tags.append({"type": "rule_id", "value": rule_id})
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
            if any(alias in question for alias in ESCALATION_ALIASES.get(name, ())):
                matched = True
                break
        if not matched:
            continue
        forbids = rule.forbid if isinstance(rule.forbid, list) else []
        if forbids:
            hints.append("涉及安全风险，请勿自行拆装或远程操作，按安全指引处理。")
    return sorted(set(hints))


def finalize(db: Session, state: State, *, history: list[dict]) -> State:
    if state.elapsed() > TOTAL_TIMEOUT_SECONDS:
        state.degraded = True
        state.decision = "REFUSE"
    if state.decision == "ANSWER":
        if not state.hits:
            state.decision = "CLARIFY" if len(state.question) < 12 else "REFUSE"
        else:
            state.citations = build_citations(state.hits)
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
                    "不确定就说明并建议转人工。回答不超过 300 字。\n\n" + context
                )},
                *history,
                {"role": "user", "content": prefix + guard + state.question},
            ]
        return state
    state.prompt_messages = state.prompt_messages or []
    state.citations = []
    return state


def run(db: Session, question: str, *, actor: dict | None, history: list[dict],
        identity_level: str = "public") -> State:
    """跑一遍编排；返回最终 state（decision/citations/prompt_messages）。"""
    state = State(question=question)
    plan(state)
    while state.steps < MAX_STEPS and state.decision == "ANSWER" and not state.hits:
        execute(db, state, actor=actor, identity_level=identity_level)
        if state.hits:
            break
        replan(db, state, actor=actor, identity_level=identity_level)
        if not state.hits or state.replans >= MAX_REPLANS:
            break
    return finalize(db, state, history=history)


def fixed_answer(state: State) -> str:
    return {
        "HANDOFF": HANDOFF_TEXT,
        "SCOPE": SCOPE_TEXT,
        "CLARIFY": CLARIFY_TEXT,
        "REFUSE": REFUSE_TEXT,
        "ANSWER": "",
    }[state.decision]
