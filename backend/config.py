"""全局配置：从 .env 读取，并推导出项目关键路径。"""
import os
from dotenv import load_dotenv

# 加载项目根目录（D:\1）下的 .env
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

# 路径
KB_DIR = os.path.join(ROOT_DIR, "kb")
RAW_DIR = os.path.join(KB_DIR, "raw")
UPLOAD_DIR = os.path.join(KB_DIR, "uploads")
VECTORSTORE_DIR = os.path.join(ROOT_DIR, "vectorstore")

os.makedirs(KB_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(VECTORSTORE_DIR, exist_ok=True)

# ============ LLM ============
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()

# DeepSeek 预设
if LLM_PROVIDER == "deepseek":
    LLM_BASE_URL = LLM_BASE_URL or "https://api.deepseek.com/v1"
    LLM_MODEL = LLM_MODEL or "deepseek-chat"

# ============ Embedding ============
EMBEDDING_API_KEY = (os.getenv("EMBEDDING_API_KEY", "") or LLM_API_KEY).strip()
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1").strip()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small").strip()

# ============ 检索 / 生成 ============
TOP_K = int(os.getenv("TOP_K", "5"))
RERANK = os.getenv("RERANK", "false").lower() == "true"

# 无 Key 时自动启用 Mock 生成器（基于检索结果抽取式回答，无需联网）
USE_MOCK_LLM = LLM_API_KEY == ""

# 向量检索始终构建（无 Key 时使用 MockEmbeddings 填充，BM25 兜底）
USE_VECTOR = True

# 默认绑定 0.0.0.0：本地仍可用 127.0.0.1 访问，部署到云/容器时也需监听 0.0.0.0
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
