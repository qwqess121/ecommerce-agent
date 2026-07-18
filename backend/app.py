"""FastAPI 服务：对话（含 SSE 流式）、知识库管理、健康检查，并托管前端。

- 前端：优先 serving frontend/dist（React 构建产物），否则回退 frontend/static
- 知识库：种子语料 + 用户条目（可增删改、富文本）；支持上传文件入库（前端显示进度）
"""
import os
import re
import json
import asyncio
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.config import HOST, PORT, USE_MOCK_LLM, UPLOAD_DIR, ROOT_DIR
from backend.agent.orchestrator import handle, reset, plan, remember, _memory
from backend.rag.generator import generate, generate_stream
from backend.kb.knowledge_store import get_store, rebuild
from backend.ingest import ingest_file
from backend.config import UPLOAD_DIR

app = FastAPI(title="WHZ 电商客服智能体 API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# 前端静态资源：优先用 React 构建产物（dist），否则回退单文件静态页
_DIST = os.path.join(ROOT_DIR, "frontend", "dist")
_STATIC = os.path.join(ROOT_DIR, "frontend", "static")
_FRONTEND_DIR = _DIST if os.path.isdir(_DIST) else _STATIC
app.mount("/ui", StaticFiles(directory=_FRONTEND_DIR, html=True), name="ui")


@app.get("/")
def root_redirect():
    return RedirectResponse("/ui/")


# ---------------- Schemas ----------------

class ChatReq(BaseModel):
    session_id: str = "default"
    message: str


class SessionReq(BaseModel):
    session_id: str = "default"


class EntryReq(BaseModel):
    title: str = ""
    html: str = ""


# ---------------- 流式打字机分块 ----------------

_PUNCT = set("，。！？、；：,.;:!? \n\t…—（）()“”\"'《》<>")
_MAX_CHUNK = 4


def chunk_text(s: str) -> list[str]:
    """把回答切成接近自然的片段，用于 SSE 流式输出（mock 模式模拟打字机）。"""
    chunks, buf = [], ""
    for ch in (s or ""):
        buf += ch
        if ch in _PUNCT or len(buf) >= _MAX_CHUNK:
            chunks.append(buf)
            buf = ""
    if buf:
        chunks.append(buf)
    return [c for c in chunks if c]


# ---------------- 接口 ----------------

@app.get("/health")
def health():
    return {"status": "ok", "mock": USE_MOCK_LLM, "store": get_store().stats()}


@app.post("/chat")
def chat(req: ChatReq):
    return handle(req.session_id, req.message)


@app.post("/chat/stream")
async def chat_stream(req: ChatReq):
    """SSE 流式对话。

    流程：先发 meta（意图/来源/转人工）-> 知识问答逐 token 流出（真实模式 astream；
    mock 模式按标点切分模拟打字机）-> 业务/闲聊/转人工直接切分既定答案 -> 发 done。
    """
    async def gen():
        p = plan(req.session_id, req.message)
        meta = {
            "intent": p["intent"],
            "sources": p["sources"],
            "transfer": p["transfer"],
            "mock": USE_MOCK_LLM,
        }
        yield f"event: meta\ndata: {json.dumps(meta, ensure_ascii=False)}\n\n"

        answer = p["answer"]  # 业务/闲聊/转人工/拦截 已确定；知识问答为 None
        history = _memory.history_text(req.session_id)

        if answer is None:
            # 知识问答：需生成。真实模式逐 token 流；mock 模式整段后切分
            if USE_MOCK_LLM:
                full = generate(req.message, p["contexts"], history)
                answer = full
                for piece in chunk_text(full):
                    yield f"event: delta\ndata: {json.dumps(piece, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.018)
            else:
                buf = ""
                async for tok in generate_stream(req.message, p["contexts"], history):
                    buf += tok
                    yield f"event: delta\ndata: {json.dumps(tok, ensure_ascii=False)}\n\n"
                answer = buf
        else:
            answer = answer or ""
            for piece in chunk_text(answer):
                yield f"event: delta\ndata: {json.dumps(piece, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.018)

        remember(req.session_id, req.message, answer or "")
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/reset")
def reset_session(req: SessionReq):
    reset(req.session_id)
    return {"ok": True}


@app.get("/kb_stats")
def kb_stats():
    return get_store().stats()


@app.get("/kb/entries")
def kb_entries():
    return {"entries": get_store().list_entries()}


@app.post("/kb/entries")
def kb_entry_add(req: EntryReq):
    if not req.html and not req.title:
        raise HTTPException(400, "标题与内容不能同时为空")
    entry = get_store().add_user_entry(req.title, req.html)
    return {"ok": True, "entry": entry}


@app.put("/kb/entries/{eid}")
def kb_entry_update(eid: str, req: EntryReq):
    entry = get_store().update_user_entry(eid, req.title, req.html)
    if not entry:
        raise HTTPException(404, "条目不存在")
    return {"ok": True, "entry": entry}


@app.delete("/kb/entries/{eid}")
def kb_entry_delete(eid: str):
    ok = get_store().delete_entry(eid)
    if not ok:
        raise HTTPException(404, "条目不存在")
    return {"ok": True, "stats": get_store().stats()}


@app.post("/rebuild")
def rebuild_kb():
    return rebuild().stats()


@app.post("/kb/upload")
async def kb_upload(file: UploadFile = File(...)):
    """上传知识文件（前端用 XHR 显示上传进度），服务端保存并重建索引。"""
    name = os.path.basename(file.filename or "upload.dat")
    path = os.path.join(UPLOAD_DIR, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name}")
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    return {"ok": True, "file": os.path.basename(path), "stats": rebuild().stats()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
