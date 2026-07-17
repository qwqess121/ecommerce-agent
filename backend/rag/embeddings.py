"""Embeddings 适配层（真正 LangChain）。

- 配置了 Embedding Key（含 DeepSeek）：使用 langchain_openai.OpenAIEmbeddings（OpenAI 兼容协议）。
- 无 Key（Mock 模式）：使用确定性的 MockEmbeddings，让向量检索也能按关键词命中，
  从而在无联网环境下完整跑通 LangChain 向量链路。
"""
import hashlib
import re
from typing import List

from langchain_core.embeddings import Embeddings

from backend.config import EMBEDDING_API_KEY, EMBEDDING_BASE_URL, EMBEDDING_MODEL

_TOKEN_RE = re.compile(r"[a-z0-9]+|[一-鿿]")


class MockEmbeddings(Embeddings):
    """确定性、可离线的嵌入：基于 token 哈希构造固定维度稠密向量。

    同一文本始终得到同一向量，使无 Key 环境下向量检索可复现、按关键词命中，
    便于端到端演示 LangChain 检索链路。
    """

    def __init__(self, dim: int = 256):
        self.dim = dim

    def _vec(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        toks = _TOKEN_RE.findall((text or "").lower())
        for tok in toks:
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            for off in range(3):
                idx = (h >> (off * 8)) % self.dim
                vec[idx] += 1.0
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._vec(text)


def get_embeddings() -> Embeddings:
    """根据配置返回真实或 Mock 的 LangChain Embeddings 实例。"""
    if EMBEDDING_API_KEY:
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            api_key=EMBEDDING_API_KEY,
            base_url=EMBEDDING_BASE_URL,
        )
    return MockEmbeddings()
