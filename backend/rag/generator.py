"""答案生成：基于 LangChain LCEL 链（prompt | llm | parser）。

- 真实模式：langchain_openai.ChatOpenAI（兼容 DeepSeek / OpenAI）
- Mock 模式：自定义 MockChatModel（继承 BaseChatModel），从检索上下文中抽取式作答，
  使无 Key 环境下也能通过完整 LangChain 链产出"基于知识库"的回答。
"""
import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_openai import ChatOpenAI

from backend.config import USE_MOCK_LLM, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

SYSTEM_PROMPT = (
    "你是某电商平台的智能客服助手，名字叫「小智」。"
    "请严格遵循以下规则：\n"
    "1. 仅依据下方【知识库内容】回答，不得编造或臆测。\n"
    "2. 若知识库没有相关信息，明确说明无法回答，并建议用户联系人工客服。\n"
    "3. 回答要简洁、友好、专业，使用与用户相同的语言。\n"
    "4. 在回答末尾用「参考来源：<来源名>」标注出处（可多个）。\n"
    "5. 遇到订单号、物流单号等需要实时数据的问题，提示需转人工或调用查询工具。"
)

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        (
            "human",
            "【历史对话】\n{history}\n\n【知识库内容】\n{context}\n\n【用户问题】\n{question}",
        ),
    ]
)


def _format_context(contexts: list[dict]) -> str:
    parts = []
    for i, c in enumerate(contexts, 1):
        src = c["metadata"].get("source", "未知")
        parts.append(f"[来源{i}]（{src}）\n{c['text']}")
    return "\n\n".join(parts)


def _mock_answer_from_prompt(text: str) -> str | None:
    """从拼好的 prompt 文本中抽取知识库第一条来源的答案。"""
    m = re.search(r"【知识库内容】\n(.*?)\n\n【用户问题】", text, re.S)
    if not m:
        return None
    ctx = m.group(1)
    am = re.search(r"答：(.*?)(?:\n\n\[来源|\Z)", ctx, re.S)
    return am.group(1).strip() if am else ctx.strip()


class MockChatModel(BaseChatModel):
    """无 Key 时的替代 LLM：实现 LangChain BaseChatModel 接口，抽取式作答。"""

    @property
    def _llm_type(self) -> str:
        return "mock-chat"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        text = ""
        for m in messages:
            text += getattr(m, "content", str(m))
        ans = _mock_answer_from_prompt(text)
        if not ans:
            ans = "抱歉，我在知识库中没有找到相关信息。建议您联系人工客服获取更准确的解答。"
        else:
            src_m = re.search(r"\[来源1\]（(.+?)）", text)
            if src_m:
                ans += f"\n\n参考来源：{src_m.group(1)}"
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=ans))]
        )


def _build_chain():
    llm = (
        MockChatModel()
        if USE_MOCK_LLM
        else ChatOpenAI(
            model=LLM_MODEL,
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            temperature=0.3,
        )
    )
    return PROMPT | llm | StrOutputParser()


def generate(question: str, contexts: list[dict], history: str = "") -> str:
    context_str = _format_context(contexts)
    chain = _build_chain()
    try:
        return chain.invoke(
            {"history": history, "context": context_str, "question": question}
        ).strip()
    except Exception as e:
        print(f"[warn] 生成失败，回退抽取式：{e}")
        if contexts:
            ans = contexts[0]["metadata"].get("answer") or contexts[0]["text"]
            src = contexts[0]["metadata"].get("source", "知识库")
            return f"{ans}\n\n参考来源：{src}"
        return "抱歉，处理失败，请联系人工客服。"
