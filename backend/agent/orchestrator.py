"""智能体编排：使用 LangGraph 构建状态机。

节点：guard_route（护栏+路由） -> rag / business / chitchat / handoff（转人工）
条件边按意图分派；blocked 直接结束并返回拒答。
RAG 节点内部调用 LangChain 混合检索 + LCEL 生成链。
"""
from typing import Optional, TypedDict

from langgraph.graph import StateGraph, START, END

from backend.config import USE_MOCK_LLM
from backend.agent.memory import ConversationMemory
from backend.agent.router import classify
from backend.agent.tools import extract_order_id, format_order, format_logistics
from backend.guardrails.guardrails import pre_check, is_relevant, safe_refuse
from backend.rag.retriever import hybrid_retrieve
from backend.rag.generator import generate

_memory = ConversationMemory()

TRANSFER_MSG = "已为您转接人工客服，请稍候，人工客服将尽快为您服务。"

CHITCHAT_REPLIES = {
    "greet": "您好！我是您的电商智能客服小智，很高兴为您服务～请问有什么可以帮您？（如订单、物流、退换货等问题都可以问我）",
    "thanks": "不客气，能帮到您是我的荣幸！如果还有其他问题，随时找我哦～",
    "default": "您好，我是智能客服小智。您可以问我关于商品、订单、物流、退换货等问题，也可以要求转接人工客服。",
}


class AgentState(TypedDict, total=False):
    session_id: str
    last_user: str
    history: str
    intent: str
    answer: str
    sources: list
    transfer: bool
    blocked: bool


def _sources_from(contexts, n=3):
    out = []
    for c in contexts[:n]:
        out.append(
            {
                "source": c["metadata"].get("source", "知识库"),
                "snippet": c["text"][:160],
            }
        )
    return out


def _handle_business(message: str):
    oid = extract_order_id(message)
    if not oid:
        return (
            "请问您能提供一下订单号或物流单号吗？（通常为 6 位以上数字）"
            "我帮您查询订单或物流信息。",
            False,
        )
    t = message.lower()
    if any(k in t for k in ["物流", "快递", "运单", "tracking", "logistics", "配送"]):
        return (format_logistics(oid) + "\n\n参考来源：订单/物流系统（mock）", False)
    return (format_order(oid) + "\n\n参考来源：订单系统（mock）", False)


def _handle_chitchat(message: str):
    t = message.lower()
    if any(k in t for k in ["谢谢", "感谢", "thanks", "thank you", "多谢"]):
        return CHITCHAT_REPLIES["thanks"], False
    if any(k in t for k in ["你好", "您好", "hi", "hello", "在吗", "哈喽"]):
        return CHITCHAT_REPLIES["greet"], False
    return CHITCHAT_REPLIES["default"], False


# ---------------- LangGraph 节点 ----------------

def guard_route(state: AgentState) -> dict:
    msg = state.get("last_user", "")
    blocked, reason = pre_check(msg)
    if blocked:
        return {
            "blocked": True,
            "intent": "blocked",
            "answer": safe_refuse(reason),
            "transfer": False,
            "sources": [],
        }
    return {"intent": classify(msg), "blocked": False}


def rag_node(state: AgentState) -> dict:
    msg = state.get("last_user", "")
    contexts = hybrid_retrieve(msg)
    answer = generate(msg, contexts, state.get("history", ""))
    sources = _sources_from(contexts)
    transfer = False
    if not is_relevant(contexts, msg):
        answer = (
            "抱歉，我在知识库中没有找到关于该问题的确切信息，"
            "为避免给您错误答复，建议转接人工客服。"
        )
        transfer = True
    return {"answer": answer, "sources": sources, "intent": "knowledge", "transfer": transfer}


def business_node(state: AgentState) -> dict:
    answer, transfer = _handle_business(state.get("last_user", ""))
    return {"answer": answer, "sources": [], "intent": "business", "transfer": transfer}


def chitchat_node(state: AgentState) -> dict:
    answer, transfer = _handle_chitchat(state.get("last_user", ""))
    return {"answer": answer, "sources": [], "intent": "chitchat", "transfer": transfer}


def handoff_node(state: AgentState) -> dict:
    return {"answer": TRANSFER_MSG, "sources": [], "intent": "human", "transfer": True}


def _route_after(state: AgentState) -> str:
    if state.get("blocked"):
        return "blocked"
    return state.get("intent", "knowledge")


def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("guard_route", guard_route)
    g.add_node("rag", rag_node)
    g.add_node("business", business_node)
    g.add_node("chitchat", chitchat_node)
    g.add_node("handoff", handoff_node)
    g.add_edge(START, "guard_route")
    g.add_conditional_edges(
        "guard_route",
        _route_after,
        {
            "knowledge": "rag",
            "business": "business",
            "chitchat": "chitchat",
            "human": "handoff",
            "blocked": END,
        },
    )
    g.add_edge("rag", END)
    g.add_edge("business", END)
    g.add_edge("chitchat", END)
    g.add_edge("handoff", END)
    return g.compile()


_GRAPH = _build_graph()


def handle(session_id: str, message: str) -> dict:
    message = (message or "").strip()
    init: AgentState = {
        "session_id": session_id,
        "last_user": message,
        "history": _memory.history_text(session_id),
        "blocked": False,
    }
    result = _GRAPH.invoke(init)
    answer = result.get("answer", "")
    sources = result.get("sources", [])
    intent = result.get("intent", "knowledge")
    transfer = result.get("transfer", False)
    _memory.add(session_id, "user", message)
    _memory.add(session_id, "assistant", answer)
    return {
        "answer": answer,
        "sources": sources,
        "intent": intent,
        "transfer": transfer,
        "mock": USE_MOCK_LLM,
    }


def reset(session_id: str):
    _memory.clear(session_id)
