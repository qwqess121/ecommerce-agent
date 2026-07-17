"""混合检索：使用 LangChain EnsembleRetriever 融合向量检索与 BM25 关键词检索。

- 向量检索：Chroma VectorStoreRetriever（langchain_chroma）
- 关键词检索：BM25Retriever（langchain_community）
- 融合：EnsembleRetriever 内部做 RRF 加权融合
返回统一结构：list[dict]，元素含 text / metadata / score。
"""
from typing import List
import re

from backend.kb.knowledge_store import get_store
from backend.config import TOP_K, USE_MOCK_LLM

# 中文逐字 + 英文词 分词器，供 BM25 使用（默认空格分词对中文无效）
_CN_TOK = re.compile(r"[a-z0-9]+|[一-鿿]")


def _tokenize_cn(text: str) -> list[str]:
    return _CN_TOK.findall((text or "").lower())


def _make_ensemble(query_docs, vectorstore, top_k):
    from backend.config import USE_MOCK_LLM

    # 构造 BM25（关键词检索，对中文 FAQ 极准；需中文逐字分词器）
    bm25 = None
    try:
        from langchain_community.retrievers import BM25Retriever

        bm25 = BM25Retriever.from_documents(
            query_docs, k=top_k * 2, tokenizer=_tokenize_cn
        )
    except Exception as e:
        print(f"[warn] BM25Retriever 构建失败：{e}")

    # Mock 模式下向量是哈希随机值、无语义，纯属噪声 -> 仅用 BM25
    if USE_MOCK_LLM:
        if bm25 is not None:
            return bm25
        if vectorstore is not None:
            return vectorstore.as_retriever(search_kwargs={"k": top_k * 2})
        return None

    # 真实模式：向量 + BM25 融合检索
    retrievers: list = []
    if vectorstore is not None:
        retrievers.append(vectorstore.as_retriever(search_kwargs={"k": top_k * 2}))
    if bm25 is not None:
        retrievers.append(bm25)
    if not retrievers:
        return None
    if len(retrievers) == 1:
        return retrievers[0]
    try:
        from langchain.retrievers import EnsembleRetriever
    except ImportError:
        try:
            from langchain_community.retrievers import EnsembleRetriever
        except ImportError:
            from langchain_classic.retrievers.ensemble import EnsembleRetriever
    return EnsembleRetriever(
        retrievers=retrievers, weights=[1.0 / len(retrievers)] * len(retrievers)
    )


def _doc_to_dict(d) -> dict:
    return {"text": d.page_content, "metadata": d.metadata, "score": 1.0}


def hybrid_retrieve(query: str, top_k: int = TOP_K) -> List[dict]:
    store = get_store()
    docs = store.get_documents()

    # Mock 模式：向量为哈希随机值（无语义），仅用 BM25 关键词检索，
    # 直接复用知识库已逐字分词的 BM25 索引，避免 langchain BM25Retriever 的中文分词缺陷。
    if USE_MOCK_LLM:
        bm25_docs = store.bm25_retrieve(query, top_k * 2)
        return [_doc_to_dict(d) for d in bm25_docs[:top_k]]

    # 真实模式：向量 + BM25 融合检索（EnsembleRetriever）
    ensemble = _make_ensemble(docs, store.get_vectorstore(), top_k)
    if ensemble is None:
        return []
    results = ensemble.invoke(query)
    out = []
    for d in results[:top_k]:
        out.append(_doc_to_dict(d))
    return out
