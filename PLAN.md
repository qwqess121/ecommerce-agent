# 电商客服智能体（RAG + Agent）实施规划

> 目标：在本项目（`D:\1`）中搭建一个**可运行的电商客服智能体原型**，基于检索增强生成（RAG）技术与智能体（Agent）编排，参考主流开源项目架构，支持商品/售后知识问答、订单/物流等业务查询、多轮对话与转人工，并配套简单管理后台与评估。

---

## 1. 范围界定

**本次交付（Prototype / Demo）**
- 知识库构建：文档加载 → 切分 → Embedding → 向量库入库
- RAG 问答核心：混合检索（向量 + 关键词）+ Reranker + 带引用生成的回答
- 智能体层：意图路由 + 多轮上下文 + 工具调用（订单/物流查询，先用 mock）+ 转人工
- 护栏：越狱防护、敏感词、相关性/拒答判断
- 前端：聊天界面（Web）+ 简单知识库管理后台
- 评估：内置测试集 + 准确率/召回人工抽检

**本期不做（后续迭代）**
- 多租户、SSO/细粒度权限、生产级鉴权与限流
- 真实业务系统对接（需提供订单/物流/商品 API）
- 高并发部署、向量库上云（Milvus/Qdrant）、模型私有化

---

## 2. 技术选型

| 层 | 选型 | 说明 |
|---|---|---|
| 后端 | Python 3.11 + FastAPI | 轻量、异步、自带 `/docs` |
| RAG 框架 | LangChain | 文档加载/切分/检索链，生态成熟 |
| 向量库 | Chroma（本地持久化） | 原型零运维；可平滑换 Milvus/Qdrant |
| Embedding | 云端 API（中文友好） | 优先 bge-large-zh / OpenAI text-embedding-3-small |
| 生成 LLM | **DeepSeek-chat（推荐）** / OpenAI gpt-4o-mini | 中文电商性价比高；API 兼容 OpenAI SDK |
| Agent 编排 | LangGraph | 意图路由 + 工具调用状态机，匹配「智能体」诉求 |
| 混合检索 | 向量 + BM25（rank_bm25） + Reranker | 提升中文召回与小样本鲁棒性 |
| 前端 | React 轻量聊天页 + 管理页（原型可先用 Gradio/Streamlit 提速） | 聊天 UI + 知识库上传 |
| 知识源 | 商品 FAQ、售后/退换货政策、店铺规则（PDF/Word/Excel/CSV/网页） | 电商场景语料 |

> 说明：「基于成熟开源项目二开」在本原型中采用 **「以开源架构为蓝本、自建聚焦实现」** 的方式——直接 fork Langchain-Chatchat / ChatWiki 体量过重（80+ 依赖、需模型服务框架），不利于快速跑通 Demo；我们复用其 RAG 流程与客服工作流设计，自建一个可定制的轻量实现，后续可平滑迁移到完整框架。

---

## 3. 系统架构

```
用户(Web/IM)
   │
   ▼
API 网关 / FastAPI
   │
   ▼
对话管理（多轮上下文 · 会话状态 · 满意度反馈）
   │
   ▼
意图识别与路由（Router Agent / LangGraph）
   ├── 知识问答（FAQ / 商品 / 政策）
   │        └─► RAG 链：查询改写 → 混合检索(向量+BM25) → Reranker → 上下文 → LLM(带引用)
   ├── 业务查询（订单 / 物流 / 库存）
   │        └─► Tool Calling → 后端 API / mock 服务
   └── 闲聊 / 其他 → 友好回应 或 转人工
   │
   ▼
护栏 Guardrails（越狱防护 · 敏感词 · 相关性/拒答）
   │
   ▼
回复 + 来源引用 + 转人工入口
   │
   ▼
管理后台（知识库上传/管理 · 对话日志 · 评估）
```

---

## 4. 核心模块设计

1. **知识库构建（Ingest）**
   - 加载：PDF / Word / Excel / CSV / 网页 / 商品库
   - 切分：按语义 + 固定窗口（中文按句号/段落切分，带重叠）
   - 向量化：Embedding 模型 → 写入 Chroma（持久化，避免重复入库）
   - 元数据：来源、类型、更新时间，便于引用与增量更新

2. **检索（Retrieval）**
   - 查询改写：多轮上下文拼装，提升指代消解
   - 混合检索：向量召回 Top-K + BM25 关键词召回，融合排序
   - Reranker：对候选重排，取最相关 N 段作为上下文
   - 无结果 / 低相关：触发拒答或转人工，避免编造

3. **生成（Generation）**
   - 客服系统 Prompt：角色设定 + 回答规范（简洁、分点、不编造）
   - 引用来源：回答附带知识出处，可点击查看
   - 防幻觉：严格基于检索上下文，未知则明说

4. **智能体层（Agent）**
   - 意图路由：知识问答 / 业务查询 / 闲聊 / 转人工
   - 工具调用：订单查询、物流跟踪、商品库存（原型用 mock 服务，接口预留）
   - 多轮管理：会话记忆、槽位填充（如订单号）
   - 转人工：高置信转接 + 上下文摘要交接

5. **护栏（Guardrails）**
   - 越狱/提示注入防护、敏感词过滤
   - 相关性检查：低相关时拒答或转人工
   - 输出安全校验

---

## 5. 实施路线图

| 阶段 | 内容 | 交付物 |
|---|---|---|
| P0 骨架 | 项目初始化、依赖、配置（`.env`）、FastAPI 启动 | 可启动后端 + 配置模板 |
| P1 知识库 | 文档加载/切分/Embedding/入库 + 电商示例知识（商品FAQ、售后政策） | 可构建并查询的向量库 |
| P2 RAG 核心 | 检索 + 生成 + 引用 + 混合检索/Reranker | `/chat` 问答接口 |
| P3 智能体 | 意图路由 + 多轮上下文 + 工具调用（订单/物流 mock）+ 转人工 | Agent 编排链路 |
| P4 护栏 | 越狱/敏感词/相关性检查 + 客服 Prompt 优化 | 安全问答 |
| P5 前端 | 聊天界面 + 知识库管理后台（上传/管理） | Web UI |
| P6 评估 | 测试集 + 准确率/召回评估 + 演示数据 | 评估报告 + Demo |

---

## 6. 参考开源项目

- **Langchain-Chatchat**（38k★，Apache-2.0）：RAG + Agent 架构、中文友好、知识库流程参考
- **ChatWiki**（芝麻小客服）：开箱即用客服问答系统、知识库管理/工作流参考
- **cs_chatbot**（joseadm）：轻量 RAG 结构（FastAPI + Chroma + React）参考
- **langgraph_multi-agent-rag-customer-support**：多智能体 + 护栏 + 人工审核参考
- **FastGPT**：可选的低代码 RAG 替代方案

---

## 7. 建议目录结构

```
D:\1\
├─ PLAN.md
├─ README.md
├─ .env.example
├─ requirements.txt
├─ backend/
│  ├─ app.py                 # FastAPI 入口
│  ├─ config.py              # 配置
│  ├─ ingest.py              # 知识库构建（加载/切分/入库）
│  ├─ rag/                   # 检索 + 生成
│  │  ├─ retriever.py        # 混合检索 + Reranker
│  │  └─ generator.py        # LLM 生成（带引用）
│  ├─ agent/                 # 智能体编排
│  │  ├─ router.py           # 意图路由
│  │  ├─ tools.py            # 工具（订单/物流 mock）
│  │  └─ orchestrator.py     # LangGraph 状态机（意图路由+Aggregate）
│  ├─ guardrails/            # 护栏
│  └─ kb/                    # 示例知识（商品FAQ、售后政策）
├─ vectorstore/              # Chroma 持久化目录
├─ frontend/                 # 聊天 UI + 管理后台
└─ eval/                     # 测试集 + 评估脚本
```

---

## 8. 风险与备注

- **API Key**：需用户提供 DeepSeek / OpenAI 的 Key（放 `.env`，不入库）
- **中文 Embedding**：建议用中文友好模型，避免中英文混合检索效果差
- **知识质量**：RAG 效果上限取决于知识库质量，需准备干净的商品/售后语料
- **自动化评估**：原型以「测试集 + 人工抽检」为主，完整指标化评估留待生产级

---

## 9. 下一步

确认本规划后，我将从 **P0（项目骨架）+ P1（知识库）+ P2（RAG 核心）** 开始，先交付一个能「上传电商知识 → 提问得到带引用回答」的最小可用闭环，再逐步补齐智能体、护栏与前端。

---

## 10. 实现进展（已落地真正 LangChain 框架）

用户确认后，核心链路已**从「轻量自建」改为真正的 LangChain 实现**，与本节技术选型完全对齐：

| 模块 | 落地实现（真正的 LangChain 组件） |
|------|----------------------------------|
| 文本切分 | `langchain_text_splitters.RecursiveCharacterTextSplitter` |
| 文档单元 | `langchain_core.documents.Document` |
| 向量库 | `langchain_chroma.Chroma` VectorStore（持久化到 `vectorstore/`） |
| Embedding | `langchain_openai.OpenAIEmbeddings`（兼容 DeepSeek）；无 Key 时用确定性 `MockEmbeddings` 兜底，保证离线可跑 |
| 混合检索 | 真实模式：`EnsembleRetriever`（`langchain_classic.retrievers.ensemble`，新版已从 `langchain.retrievers` 迁移）融合 `VectorStoreRetriever` + `BM25Retriever`；**Mock 模式**：向量为哈希随机值（无语义），仅用 BM25 关键词检索（直接复用知识库已逐字分词的 `BM25Okapi` 索引，绕开 langchain `BM25Retriever` 的中文空格分词缺陷） |
| 生成链 | LCEL：`ChatPromptTemplate \| ChatOpenAI \| StrOutputParser`；无 Key 用自定义 `MockChatModel(BaseChatModel)` |
| 业务工具 | `@tool` 装饰的 LangChain 工具（`order_query_tool` / `logistics_query_tool`） |
| 智能体编排 | `langgraph.graph.StateGraph` 状态机（guard→route→rag/business/chitchat/handoff） |

**双模式说明**：系统支持「有 Key 走真实 LLM，无 Key 走 Mock 生成器」。Mock 模式通过 `MockEmbeddings` + `MockChatModel` 完整跑通 LangChain 检索/生成/编排链路（抽取式作答），便于无 Key 环境下端到端验证；用户在 `.env` 填入 Key 后即获得真实大模型回答。

**知识来源**：已接入开源电商客服数据集 `Andyrasika/Ecommerce_FAQ`（79 条）+ `MakTek/Customer_support_faqs`（200 条）+ 中文种子知识（53 条），共 332+ 条真实 Q&A；并支持上传自有知识库（`/ingest`）增量重建。

---

## 11. 落地状态与运行方式（截至 2026-07-17）

**已完成并自测通过（端到端评测 12/12 = 100%）**：
- P0 项目骨架 + 隔离 venv + FastAPI 启动 ✓
- P1 知识库构建（加载/切分/入库 Chroma）✓
- P2 RAG 检索 + 生成 + 引用 ✓
- P3 LangGraph 智能体编排（路由/工具/多轮/转人工）✓
- P4 护栏（越狱/敏感词/相关性拒答）✓
- P5 Gradio 聊天前端 + 知识库管理（上传）✓
- P6 评测脚本 + 报告 ✓

**运行方式**：
```bash
# 1) 安装依赖（国内务必用镜像，见下方「踩坑」）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2) 配置（可选，不填则用 Mock 模式）
cp .env.example .env   # 填入 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL

# 3) 构建知识库（首次或变更语料后）
PYTHONPATH=. python -c "from backend.ingest import rebuild; print(rebuild().stats())"

# 4) 启动（后端 + Gradio 前端）
python run.py            # 或分别启动 backend.app:app 与 frontend.app
```

**评测**：`python eval/run_eval.py`（需后端在 8000 端口运行），结果见 `eval/report.md`。

**踩坑记录（重要）**：
1. **PyPI 直连卡死**：`files.pythonhosted.org` 大文件下载在境内会挂起，导致 `pip install` 看似「假死」。解决：统一用清华/阿里云镜像 `-i https://pypi.tuna.tsinghua.edu.cn/simple`。
2. **新版 LangChain 包路径迁移**：`langchain` 元包已不提供顶层 `langchain.retrievers`；`EnsembleRetriever` 在 `langchain_classic.retrievers.ensemble`，`BM25Retriever` 在 `langchain_community.retrievers`（且该包的 `BM25Retriever` 默认空格分词对中文无效，需用 `langchain_classic` 或自管 `BM25Okapi` 并传中文分词器）。已把 `langchain-classic` 加入 `requirements.txt`。
3. **Mock 模式检索**：Mock Embeddings 是哈希随机值、无语义，向量检索纯噪声；故 Mock 模式仅用 BM25 逐字检索，保证中文 FAQ 召回准确。

**效果说明**：Mock 模式下回答为「抽取式」（直接引用最相关知识片段），中文问答已连贯准确；填入真实 LLM Key 后，将获得基于上下文生成的自然语言回答，且跨语言（中→英）检索质量显著提升。
