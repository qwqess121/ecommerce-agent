"""FastAPI 服务：对话、知识库管理、健康检查，并托管前端静态页面。"""
import os

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.config import HOST, PORT, USE_MOCK_LLM
from backend.agent.orchestrator import handle, reset
from backend.kb.knowledge_store import get_store, rebuild
from backend.ingest import ingest_file
from backend.config import UPLOAD_DIR

app = FastAPI(title="电商客服智能体 API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# 前端静态资源（自包含聊天界面）
_FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "static")
app.mount("/ui", StaticFiles(directory=_FRONTEND_DIR, html=True), name="ui")


@app.get("/")
def root_redirect():
    return RedirectResponse("/ui/")


class ChatReq(BaseModel):
    session_id: str = "default"
    message: str


class SessionReq(BaseModel):
    session_id: str = "default"


@app.get("/health")
def health():
    return {"status": "ok", "mock": USE_MOCK_LLM, "store": get_store().stats()}


@app.post("/chat")
def chat(req: ChatReq):
    return handle(req.session_id, req.message)


@app.post("/reset")
def reset_session(req: SessionReq):
    reset(req.session_id)
    return {"ok": True}


@app.get("/kb_stats")
def kb_stats():
    return get_store().stats()


@app.post("/rebuild")
def rebuild_kb():
    return rebuild().stats()


@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    # 保存到 uploads 并重建索引
    path = os.path.join(UPLOAD_DIR, file.filename)
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    return rebuild().stats()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
