# WHZ 电商客服智能体（RAG + Agent）

基于检索增强生成（RAG）与智能体（Agent）的电商客服系统，前端为 **React + Vite** 工程化版本，后端为 **FastAPI + LangChain + Chroma**。参考 Langchain-Chatchat / ChatWiki / cs_chatbot 等开源项目设计。

> 品牌：WHZ（主色 `#6C5CE7 → #00CEC9` 渐变）。可在 `frontend/src/index.css` 与 `frontend/src/components/Logo.jsx` 中修改。

## 功能特性

- **知识问答（RAG）**：混合检索（BM25 关键词 + Chroma 向量，RRF 融合）+ 带引用来源的生成
- **流式输出（打字机）**：后端 `POST /chat/stream`（SSE），前端逐字渲染
- **语音输入**：Web Speech API（`zh-CN`），不支持的浏览器自动降级
- **深色模式**：一键切换，持久化到 `localStorage`，首次跟随系统
- **业务查询（Agent 工具）**：订单 / 物流查询（mock，接口预留真实 API）
- **意图路由**：知识问答 / 业务查询 / 闲聊 / 转人工
- **护栏**：越狱 / 提示注入防护、相关性拒答
- **知识库管理**：前端面板支持上传（带进度条）、删除某条、富文本（加粗/斜体/列表/链接）新增与编辑
- **双模式**：无 API Key 走 Mock 生成器（可离线演示），填 Key 即真实大模型回答

## 快速开始（本机）

```bash
# 1. 安装 Python 依赖（建议隔离 venv）
pip install -r requirements.txt

# 2. 安装前端依赖并构建（产出 frontend/dist，由后端托管）
cd frontend && npm install && npm run build && cd ..

# 3. 启动后端（同时托管 API 与前端）
python run.py
#    打开 http://127.0.0.1:8000/ui/
```

无 API Key 也能完整运行：系统自动启用 **Mock 生成器**（基于检索结果抽取式回答），用于验证检索、接口、UI 全链路。填入 Key 后即获得真实大模型回答。

可选配置：复制 `.env.example` 为 `.env`，填入 `LLM_API_KEY`（DeepSeek / OpenAI 兼容）、`LLM_BASE_URL`、`EMBEDDING_API_KEY` 等。

## 双模式说明

| 配置 | 行为 |
|------|------|
| 无 `LLM_API_KEY` | Mock 生成器：直接返回检索到的答案片段（可离线、可测） |
| 有 `LLM_API_KEY` | 真实 LLM（OpenAI / DeepSeek 兼容）生成回答 |
| 无 `EMBEDDING_API_KEY` | 仅 BM25 关键词检索（无需联网） |
| 有 `EMBEDDING_API_KEY` | 额外启用 Chroma 向量检索，RRF 融合提升召回 |

## 知识库数据来源

- **开源数据（训练语料）**：真实电商客服 Q&A 数据集，存于 `kb/raw/`：
  - `Andyrasika/Ecommerce_FAQ`（79 条）
  - `MakTek/Customer_support_faqs_dataset`（200 条）
  - 共 **279 条** 问答，构成初始知识库。
- **中文种子知识**：`kb/chinese_ecommerce_faq.json`（退货/物流/支付等），便于中文演示，可自由增删。
- **用户自有知识**：在「知识库」面板上传文件（JSON/JSONL/TXT/MD/CSV），或调用 `POST /kb/upload`，自动重建索引；也可在面板新增/编辑/删除富文本条目。

## 目录结构

```
D:\1\
├─ run.py                 # 一键启动 FastAPI（托管 API + 前端 dist）
├─ requirements.txt
├─ render.yaml            # Render Blueprint 部署配置
├─ .env.example
├─ backend/
│  ├─ config.py           # 配置与路径
│  ├─ app.py              # FastAPI 接口（含 /chat/stream、/kb/entries）
│  ├─ ingest.py           # 知识库构建 / 入库
│  ├─ rag/                # retriever / generator / embeddings / splitter
│  ├─ agent/              # orchestrator(LangGraph) / router / tools / memory
│  ├─ guardrails/         # 护栏
│  └─ kb/                 # 知识加载、索引、用户条目管理
├─ frontend/              # React + Vite 工程（src/ 组件化，build 产出 dist/）
├─ kb/                    # 知识源（raw 开源数据 + 中文种子 + uploads）
├─ vectorstore/           # Chroma 持久化（启用向量时，部署会自动重建）
└─ eval/                  # 测试集 + 评估脚本
```

## API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/health` | 健康检查 + 索引统计 |
| POST | `/chat` | `{session_id, message}` → 回答/来源/意图/转人工 |
| POST | `/chat/stream` | SSE 流式：`meta → delta → done` |
| POST | `/reset` | 清空某会话记忆 |
| GET  | `/kb_stats` | 知识库统计 |
| GET  | `/kb/entries` | 列出全部知识条目（种子 / 用户） |
| POST | `/kb/entries` | 新增用户富文本条目 |
| PUT  | `/kb/entries/{id}` | 编辑某条 |
| DELETE | `/kb/entries/{id}` | 删除某条（用户条目直接删，种子条目加入排除列表） |
| POST | `/kb/upload` | 上传文件入库 |
| POST | `/rebuild` | 重建索引 |

## 评估

```bash
# 先启动后端（python run.py），另开终端：
python eval/run_eval.py
```

对 `eval/testset.json` 12 条用例做端到端校验，输出通过率与 `eval/report.md`（当前 12/12 通过）。

## 部署（Render，免费）

仓库根目录已包含 `render.yaml`（Blueprint）：免费计划、Python 3.13、`pip install` 安装依赖、`uvicorn backend.app:app --host 0.0.0.0 --port $PORT` 启动、`/health` 健康检查。

在 [render.com](https://render.com) → **New → Blueprint** → 连接本仓库即可自动部署，获得公开链接（默认 Mock 模式，无需 API Key 即可访问）。免费版闲置 15 分钟后休眠，首次访问需 30–60 秒唤醒并自动重建索引。

## 接入真实系统（预留位）

- **业务工具**：`backend/agent/tools.py` 的 `query_order` / `query_logistics` 当前返回 mock，替换为订单中心 / 物流商 API 即可。
- **大模型**：`backend/config.py` + `.env` 切换 DeepSeek / OpenAI。
- **向量库**：当前 Chroma 本地；规模化可换 Milvus / Qdrant（改 `knowledge_store.py`）。
- **生产化**：补充鉴权、限流、多租户、会话日志与人工客服工作台（本期未做）。
