"""智能体编排：确定性规划器（路由 + 检索 + 生成分派）。

- 意图路由：知识问答 / 业务查询 / 闲聊 / 转人工 / 拦截
- 知识问答：LangChain 混合检索（Chroma 向量 + BM25）-> LCEL 生成链
- 真实 LLM 模式可经 /chat/stream 逐 token 流出；mock 模式抽取式作答
LangChain 核心组件：langchain_chroma(VectorStore)、EnsembleRetriever、LCEL(PROMPT|llm|StrOutputParser)、@tool(业务工具)。
"""
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


# ---------------- 编排（确定性规划器） ----------------


def plan(session_id: str, message: str) -> dict:
    """路由 + 检索的「规划」阶段，供 handle() 与流式接口复用。

    返回：{ intent, answer, sources, transfer, contexts, blocked }
    - 知识问答：answer 为 None（需后续生成），contexts 为检索结果
    - 业务/闲聊/转人工/拦截：answer 已确定，contexts 为空
    """
    message = (message or "").strip()
    blocked, reason = pre_check(message)
    if blocked:
        return {
            "intent": "blocked",
            "answer": safe_refuse(reason),
            "sources": [],
            "transfer": False,
            "contexts": [],
            "blocked": True,
        }
    intent = classify(message)
    contexts: list = []
    transfer = False
    answer = None
    if intent == "knowledge":
        contexts = hybrid_retrieve(message)
        if not is_relevant(contexts, message):
            answer = (
                "抱歉，我在知识库中没有找到关于该问题的确切信息，"
                "为避免给您错误答复，建议转接人工客服。"
            )
            transfer = True
    elif intent == "business":
        answer, transfer = _handle_business(message)
    elif intent == "human":
        answer = TRANSFER_MSG
        transfer = True
    else:  # chitchat
        answer, transfer = _handle_chitchat(message)
    sources = _sources_from(contexts) if contexts else []
    return {
        "intent": intent,
        "answer": answer,
        "sources": sources,
        "transfer": transfer,
        "contexts": contexts,
        "blocked": False,
    }


def handle(session_id: str, message: str) -> dict:
    message = (message or "").strip()
    p = plan(session_id, message)
    answer = p["answer"]
    if answer is None:  # 知识问答需要生成
        answer = generate(message, p["contexts"], _memory.history_text(session_id))
    remember(session_id, message, answer)
    return {
        "answer": answer,
        "sources": p["sources"],
        "intent": p["intent"],
        "transfer": p["transfer"],
        "mock": USE_MOCK_LLM,
    }


def remember(session_id: str, user_msg: str, answer: str):
    """把一轮对话写入多轮记忆（供 handle 与流式接口共用）。"""
    _memory.add(session_id, "user", user_msg)
    _memory.add(session_id, "assistant", answer)


def reset(session_id: str):
    _memory.clear(session_id)
