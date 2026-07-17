"""知识库构建 / 增量入库。

- build()：扫描 kb/ 下全部源文件，重建索引（BM25 + 可选向量）。
- ingest_file(path)：将用户上传文件拷贝到 kb/uploads/ 并重建。
"""
import os
import shutil

from backend.config import UPLOAD_DIR
from backend.kb.knowledge_store import rebuild


def build() -> dict:
    return rebuild().stats()


def ingest_file(src_path: str) -> dict:
    name = os.path.basename(src_path)
    dest = os.path.join(UPLOAD_DIR, name)
    shutil.copy(src_path, dest)
    return rebuild().stats()


if __name__ == "__main__":
    print("重建知识库...")
    print(build())
