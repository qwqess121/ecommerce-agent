"""一键启动：启动 FastAPI 后端（同时托管前端界面 /ui）。

访问地址：
  - 前端聊天界面：http://127.0.0.1:8000/ui/
  - 后端 API 文档：http://127.0.0.1:8000/docs
"""
import uvicorn

from backend.config import HOST, PORT


if __name__ == "__main__":
    uvicorn.run("backend.app:app", host=HOST, port=PORT, log_level="info")
