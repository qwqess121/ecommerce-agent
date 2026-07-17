"""中文友好的文本切分。"""
from langchain_text_splitters import RecursiveCharacterTextSplitter


def make_splitter(chunk_size: int = 400, chunk_overlap: int = 50):
    # 针对中英文混合：优先按段落/句子/标点切分
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "；", "；", ".", "!", "?", "，", ",", " ", ""],
        keep_separator=True,
    )


def split_texts(texts, metadatas, chunk_size=400, chunk_overlap=50):
    splitter = make_splitter(chunk_size, chunk_overlap)
    out_docs, out_meta = [], []
    for text, meta in zip(texts, metadatas):
        chunks = splitter.split_text(text)
        for i, c in enumerate(chunks):
            m = dict(meta)
            m["chunk_index"] = i
            out_docs.append(c)
            out_meta.append(m)
    return out_docs, out_meta
