# 电商客服智能体（RAG + Agent）

基于检索增强生成（RAG）与智能体（Agent）的电商客服原型，参考 Langchain-Chatchat / ChatWiki / cs_chatbot 等开源项目设计。支持：

- **知识问答（RAG）**：混合检索（BM25 关键词 + 可选向量检索）+ 带引用生成
- **业务查询（Agent 工具）**：订单 / 物流查询（mock，接口预留真实 API）
- **多轮对话**：按会话维护上下文
- **意图路由**：知识问答 / 业务查询 / 闲聊 / 转人工
- **护栏**：越狱/提示注入防护、敏感词、相关性拒答
- **可私有上传知识库**：上传 JSON/JSONL/TXT/MD/CSV 自动重建索引

## 快速开始

```bash
# 1. 安装依赖（已用隔离 venv，见下）
pip install -r requirements.txt

# 2. 配置（可选，不填则自动走 Mock 模式）
cp .env.example .env
#   编辑 .env 填入 LLM_API_KEY（DeepSeek / OpenAI 均可）

# 3. 一键启动（同时拉起 FastAPI + Gradio）
python run.py
#   打开 http://127.0.0.1:7860
```

无 API Key 也能完整运行：系统自动启用 **Mock 生成器**（基于检索结果抽取式回答），用于验证检索、接口、UI 全链路。填入 Key 后即获得真实大模型回答。

## 双模式说明

| 配置 | 行为 |
|------|------|
| 无 `LLM_API_KEY` | Mock 生成器：直接返回检索到的答案片段（可离线、可测） |
| 有 `LLM_API_KEY` | 真实 LLM（OpenAI / DeepSeek 兼容）生成回答 |
| 无 `EMBEDDING_API_KEY` | 仅 BM25 关键词检索（无需联网） |
| 有 `EMBEDDING_API_KEY` | 额外启用 Chroma 向量检索，RRF 融合提升召回 |

## 知识库数据来源

- **开源数据（训练语料）**：从 HuggingFace 下载的真实电商客服 Q&A 数据集，已存于 `kb/raw/`：
  - `Andyrasika/Ecommerce_FAQ`（79 条）
  - `MakTek/Customer_support_faqs_dataset`（200 条）
  - 共 **279 条** 问答，构成初始知识库。
- **中文种子知识**：`kb/chinese_ecommerce_faq.json`（退货/物流/支付等 12 条），便于中文演示，可自由增删。
- **自有知识库**：在 Gradio「知识库管理」页上传文件，或放入 `kb/uploads/`，自动重建索引。

> 后期接入你自己的知识库：直接上传业务文档（商品手册、售后政策、FAQ 等）即可，无需改代码。

## 目录结构

```
D:\1\
├─ run.py                 # 一键启动（FastAPI + Gradio）
├─ requirements.txt
├─ .env.example
├─ backend/
│  ├─ config.py           # 配置与路径
│  ├─ app.py              # FastAPI 接口
│  ├─ ingest.py           # 知识库构建/入库
│  ├─ rag/                # retriever / generator / embeddings / splitter
│  ├─ agent/              # orchestrator / router / tools / memory
│  ├─ guardrails/         # 护栏
│  └─ kb/                 # 知识加载与索引（knowledge_store）
├─ frontend/app.py        # Gradio 聊天 + 知识库管理
├─ kb/                    # 知识源（raw 开源数据 + 中文种子 + uploads）
├─ vectorstore/           # Chroma 持久化（启用向量时）
└─ eval/                  # 测试集 + 评估脚本
```

## API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/health` | 健康检查 + 索引统计 |
| POST | `/chat` | `{session_id, message}` → 回答/来源/意图/转人工 |
| POST | `/reset` | 清空某会话记忆 |
| GET  | `/kb_stats` | 知识库统计 |
| POST | `/rebuild` | 重建索引 |
| POST | `/ingest` | 上传文件并入库 |

## 评估

```bash
# 先启动后端（python run.py），另开终端：
python eval/run_eval.py
```

对 `eval/testset.json` 12 条用例做端到端校验，输出通过率与 `eval/report.md`。

## 接入真实系统（预留位）

- **业务工具**：`backend/agent/tools.py` 的 `query_order` / `query_logistics` 当前返回 mock，替换为订单中心 / 物流商 API 即可。
- **大模型**：`backend/config.py` + `.env` 切换 DeepSeek / OpenAI。
- **向量库**：当前 Chroma 本地；规模化可换 Milvus / Qdrant（改 `knowledge_store.py`）。
- **生产化**：补充鉴权、限流、多租户、会话日志与人工客服工作台（本期未做）。
