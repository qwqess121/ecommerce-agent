"""知识库：加载 -> 切分 -> LangChain Document -> Chroma 向量库 + BM25 关键词索引。

使用真正的 LangChain 组件：
- langchain_core.documents.Document 作为统一文档单元
- langchain_chroma.Chroma 作为向量存储（持久化到本地）
- rank_bm25 构建关键词索引，供 EnsembleRetriever 做混合检索
"""
import os
import re
import json
import glob
from datetime import datetime

from langchain_core.documents import Document
from langchain_chroma import Chroma
from rank_bm25 import BM25Okapi

from backend.config import KB_DIR, RAW_DIR, UPLOAD_DIR, VECTORSTORE_DIR, TOP_K
from backend.rag.splitter import split_texts
from backend.rag.embeddings import get_embeddings

_TOKEN_RE = re.compile(r"[a-z0-9]+|[一-鿿]")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


# ---------------- 文档加载（与具体格式解耦） ----------------

def _qa_to_doc(rec: dict, source: str) -> tuple[str, dict]:
    q = str(rec.get("question") or rec.get("q") or "").strip()
    a = str(rec.get("answer") or rec.get("a") or "").strip()
    text = f"问：{q}\n答：{a}" if (q and a) else (q or a)
    meta = {"source": source, "type": "faq", "question": q, "answer": a}
    return text, meta


def _load_qa_file(path: str) -> list[tuple[str, dict]]:
    """加载 question/answer 形式的 JSON 或 JSONL（兼容两种格式）。"""
    out = []
    with open(path, encoding="utf-8") as f:
        raw = f.read().strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        for rec in data:
            out.append(_qa_to_doc(rec, os.path.basename(path)))
        return out
    except json.JSONDecodeError:
        pass
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(_qa_to_doc(json.loads(line), os.path.basename(path)))
        except Exception:
            continue
    return out


def _load_text_file(path: str) -> list[tuple[str, dict]]:
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = f.read()
    return [(text, {"source": os.path.basename(path), "type": "doc"})]


def _load_csv_file(path: str) -> list[tuple[str, dict]]:
    import csv

    out = []
    with open(path, encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            text = " | ".join(f"{k}: {v}" for k, v in row.items() if v)
            out.append((text, {"source": os.path.basename(path), "type": "csv", "row": i}))
    return out


def load_raw() -> tuple[list[str], list[dict]]:
    """扫描 kb 目录下的所有源文件，返回 (texts, metadatas)。"""
    docs, metas = [], []
    patterns = {
        "**/*.json": _load_qa_file,
        "**/*.jsonl": _load_qa_file,
        "**/*.txt": _load_text_file,
        "**/*.md": _load_text_file,
        "**/*.csv": _load_csv_file,
    }
    for pat, loader in patterns.items():
        for path in glob.glob(os.path.join(KB_DIR, pat), recursive=True):
            try:
                for text, meta in loader(path):
                    docs.append(text)
                    metas.append(meta)
            except Exception as e:
                print(f"[warn] 跳过文件 {path}: {e}")
    return docs, metas


def build_documents() -> list[Document]:
    """把原始文本转换为 LangChain Document（FAQ 整体成块，普通文本切分）。"""
    texts, metas = load_raw()
    documents: list[Document] = []
    for t, m in zip(texts, metas):
        if m.get("type") == "faq":
            documents.append(Document(page_content=t, metadata=m))
        else:
            st, sm = split_texts([t], [m])
            for c, cm in zip(st, sm):
                documents.append(Document(page_content=c, metadata=cm))
    return documents


# ---------------- 知识库索引 ----------------

class KnowledgeStore:
    def __init__(self):
        self.built_at = None
        self.docs: list[Document] = []
        self._bm25 = None
        self._vectorstore: Chroma | None = None
        self._build()

    def _build(self):
        self.docs = build_documents()
        # BM25 关键词索引（始终构建）
        if self.docs:
            self._bm25 = BM25Okapi([tokenize(d.page_content) for d in self.docs])
        else:
            print("[warn] 知识库为空，BM25 未构建")
            self._bm25 = None
        # Chroma 向量索引（LangChain VectorStore，持久化）
        try:
            embed = get_embeddings()
            # 先清空旧集合再重建，避免 id 冲突
            try:
                Chroma(
                    collection_name="cs_kb",
                    embedding_function=embed,
                    persist_directory=VECTORSTORE_DIR,
                ).delete_collection()
            except Exception:
                pass
            self._vectorstore = Chroma(
                collection_name="cs_kb",
                embedding_function=embed,
                persist_directory=VECTORSTORE_DIR,
            )
            self._vectorstore.add_documents(
                self.docs, ids=[f"doc{i}" for i in range(len(self.docs))]
            )
        except Exception as e:
            print(f"[warn] Chroma 向量索引构建失败，将仅使用 BM25：{e}")
            self._vectorstore = None
        self.built_at = datetime.now().isoformat()

    # ---------------- 对外访问 ----------------

    def get_documents(self) -> list[Document]:
        return self.docs

    def bm25_retrieve(self, query: str, top_k: int = 5) -> list[Document]:
        """基于已建好的 BM25 索引做关键词检索（中文逐字分词，对 FAQ 极准）。"""
        if self._bm25 is None or not self.docs:
            return []
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        scores = self._bm25.get_scores(q_tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [self.docs[i] for i in ranked[:top_k] if scores[i] > 0]

    def get_vectorstore(self) -> Chroma | None:
        return self._vectorstore

    def stats(self) -> dict:
        return {
            "documents": len({d.metadata.get("source") for d in self.docs}),
            "chunks": len(self.docs),
            "vector_enabled": self._vectorstore is not None,
            "built_at": self.built_at,
        }


# ---------------- 单例 ----------------

_STORE: KnowledgeStore | None = None


def get_store() -> KnowledgeStore:
    global _STORE
    if _STORE is None:
        _STORE = KnowledgeStore()
    return _STORE


def rebuild() -> KnowledgeStore:
    global _STORE
    _STORE = KnowledgeStore()
    return _STORE
