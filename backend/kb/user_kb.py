"""用户知识库：可增删改的条目（支持富文本 HTML），与种子语料分离管理。

- 用户条目持久化到 kb/user_entries.json（稳定 id、标题、HTML 原文、纯文本）
- 种子条目删除采用「排除列表」kb/excluded_seed.json（不改原始语料文件）
- html_to_text 把富文本 HTML 转为用于向量化的纯文本
"""
import os
import re
import json
import uuid
from datetime import datetime

from backend.config import KB_DIR

USER_FILE = os.path.join(KB_DIR, "user_entries.json")
EXCLUDED_FILE = os.path.join(KB_DIR, "excluded_seed.json")

_ENTITIES = [
    ("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
    ("&quot;", '"'), ("&apos;", "'"), ("&#39;", "'"), ("&nbsp", " "),
]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def html_to_text(html: str) -> str:
    """把富文本 HTML 转为纯文本（保留段落换行）。"""
    if not html:
        return ""
    # 去掉 script / style
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    # 块级标签 -> 换行
    h = re.sub(r"<br\s*/?>|</p>|</div>|</h[1-6]>|</li>|</tr>", "\n", h, flags=re.I)
    # 去所有剩余标签
    text = re.sub(r"<[^>]+>", "", h)
    for a, b in _ENTITIES:
        text = text.replace(a, b)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def load_user() -> list:
    if not os.path.exists(USER_FILE):
        return []
    try:
        with open(USER_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_user(items: list):
    os.makedirs(os.path.dirname(USER_FILE), exist_ok=True)
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def load_excluded() -> list:
    if not os.path.exists(EXCLUDED_FILE):
        return []
    try:
        with open(EXCLUDED_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_excluded(ids: list):
    os.makedirs(os.path.dirname(EXCLUDED_FILE), exist_ok=True)
    with open(EXCLUDED_FILE, "w", encoding="utf-8") as f:
        json.dump(ids, f, ensure_ascii=False, indent=2)


def add_entry(title: str, html: str) -> dict:
    items = load_user()
    entry = {
        "id": "u_" + uuid.uuid4().hex[:12],
        "title": (title or "").strip(),
        "html": html or "",
        "text": html_to_text(html),
        "created_at": _now(),
        "updated_at": _now(),
    }
    items.append(entry)
    save_user(items)
    return entry


def update_entry(eid: str, title: str, html: str) -> dict | None:
    items = load_user()
    for it in items:
        if it["id"] == eid:
            it["title"] = (title or "").strip()
            it["html"] = html or ""
            it["text"] = html_to_text(html)
            it["updated_at"] = _now()
            save_user(items)
            return it
    return None


def delete_user_entry(eid: str) -> bool:
    items = load_user()
    new = [it for it in items if it["id"] != eid]
    if len(new) != len(items):
        save_user(new)
        return True
    return False


def exclude_seed(sid: str):
    ex = load_excluded()
    if sid not in ex:
        ex.append(sid)
        save_excluded(ex)


def unexclude_seed(sid: str):
    ex = load_excluded()
    if sid in ex:
        ex.remove(sid)
        save_excluded(ex)
