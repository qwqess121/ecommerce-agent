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
from backend.kb import user_kb

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
    """把原始文本 + 用户知识库转换为 LangChain Document。

    - 种子语料（kb/ 下文件）按稳定 id `seed::{i}` 编号，排除 excluded 列表中的条目
    - 用户条目用 id `user::{entry_id}`，富文本 HTML 已转为纯文本
    - 每条 Document 的 metadata._id / _title 用于条目级管理与前端展示
    """
    texts, metas = load_raw()
    documents: list[Document] = []
    excluded = set(user_kb.load_excluded())
    idx = 0
    for t, m in zip(texts, metas):
        sid = f"seed::{idx}"
        idx += 1
        if sid in excluded:
            continue
        title = m.get("question") or (t[:40])
        if m.get("type") == "faq":
            documents.append(Document(
                page_content=t,
                metadata={**m, "_id": sid, "_title": title},
            ))
        else:
            st, sm = split_texts([t], [m])
            for c, cm in zip(st, sm):
                documents.append(Document(
                    page_content=c,
                    metadata={**cm, "_id": sid, "_title": m.get("source", "doc")},
                ))
    # 用户知识库
    for e in user_kb.load_user():
        documents.append(Document(
            page_content=e["text"] or e["title"],
            metadata={
                "source": "用户知识库",
                "type": "user",
                "_id": "user::" + e["id"],
                "_title": e["title"] or (e["text"][:40]),
                "_html": e.get("html", ""),
                "_created": e.get("created_at", ""),
            },
        ))
    return documents


# ---------------- 知识库索引 ----------------

class KnowledgeStore:
    def __init__(self):
        self.built_at = None
        self.docs: list[Document] = []
        self._ids: list[str] = []
        self._bm25 = None
        self._vectorstore: Chroma | None = None
        self._build()

    def _build(self):
        self.docs = build_documents()
        self._ids = [d.metadata.get("_id", f"doc{i}") for i, d in enumerate(self.docs)]
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
            self._vectorstore.add_documents(self.docs, ids=self._ids)
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

    # ---------------- 条目级管理（供前端知识库面板） ----------------

    def list_entries(self) -> list[dict]:
        """返回条目级清单（按 _id 去重，FAQ 多分块归并到同一 _id）。"""
        seen: set[str] = set()
        out: list[dict] = []
        for d in self.docs:
            mid = d.metadata.get("_id", "")
            if mid in seen:
                continue
            seen.add(mid)
            kind = "user" if mid.startswith("user::") else "seed"
            out.append({
                "id": mid,
                "title": d.metadata.get("_title") or d.page_content[:40],
                "snippet": d.page_content[:140],
                "kind": kind,
                "source": d.metadata.get("source", ""),
                "html": d.metadata.get("_html", ""),
                "created": d.metadata.get("_created", ""),
            })
        return out

    def delete_entry(self, eid: str) -> bool:
        if eid.startswith("user::"):
            ok = user_kb.delete_user_entry(eid.split("::", 1)[1])
        elif eid.startswith("seed::"):
            user_kb.exclude_seed(eid)
            ok = True
        else:
            # 兼容 add_user_entry 返回的纯 user id（不含 "user::" 前缀）
            if user_kb.delete_user_entry(eid):
                ok = True
            else:
                user_kb.exclude_seed("seed::" + eid)
                ok = True
        if ok:
            self._build()
        return ok

    def add_user_entry(self, title: str, html: str) -> dict:
        entry = user_kb.add_entry(title, html)
        self._build()
        return entry

    def update_user_entry(self, eid: str, title: str, html: str) -> dict | None:
        entry = user_kb.update_entry(eid, title, html)
        if entry:
            self._build()
        return entry

    def stats(self) -> dict:
        user_n = len([d for d in self.docs if d.metadata.get("_id", "").startswith("user::")])
        return {
            "documents": len({d.metadata.get("source") for d in self.docs}),
            "chunks": len(self.docs),
            "user_entries": user_n,
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
