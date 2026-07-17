"""极简多轮对话记忆（按会话 ID 存储）。"""
from collections import defaultdict

_MAX_TURNS = 12  # 保留最近 N 轮（含 user+assistant）


class ConversationMemory:
    def __init__(self):
        self._store = defaultdict(list)

    def add(self, session_id: str, role: str, content: str):
        self._store[session_id].append({"role": role, "content": content})
        # 裁剪
        if len(self._store[session_id]) > _MAX_TURNS * 2:
            self._store[session_id] = self._store[session_id][-_MAX_TURNS * 2:]

    def get(self, session_id: str):
        return self._store[session_id]

    def history_text(self, session_id: str, max_turns: int = 4) -> str:
        msgs = self._store[session_id][-max_turns * 2:]
        return "\n".join(f"{m['role']}: {m['content']}" for m in msgs)

    def clear(self, session_id: str):
        self._store[session_id] = []
