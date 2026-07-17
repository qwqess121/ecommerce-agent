"""护栏：越狱/提示注入防护、敏感词、相关性拒答。"""
import re

# 越狱 / 提示注入常见模式
JAILBREAK_PATTERNS = [
    r"忽略(之前|以上|上述|所有).{0,6}?(指令|规则|prompt|提示)",
    r"ignore (all|the|previous|above).{0,20}?instructions?",
    r"你现在是(一|另)个?没有限制的",
    r"(pretend|act) (as|like) (a|an) .{0,20}?(without|no) (rules|restrictions)",
    r"developer mode",
    r"d?an mode",
    r"越狱",
    r"输出你的(系统)?提示(词)?",
    r"what is your (system )?prompt",
]

# 敏感词（示例，可按业务扩展）
SENSITIVE_WORDS = ["违禁", "毒品", "赌博", "枪支", "走私"]

_JB_RE = [re.compile(p, re.IGNORECASE) for p in JAILBREAK_PATTERNS]


def pre_check(text: str) -> tuple[bool, str]:
    """返回 (是否拦截, 原因)。"""
    t = text or ""
    for r in _JB_RE:
        if r.search(t):
            return True, "检测到越狱/提示注入尝试"
    for w in SENSITIVE_WORDS:
        if w in t:
            return True, "包含敏感词"
    return False, ""


_TOKEN_RE = re.compile(r"[a-z0-9]+|[一-鿿]")


def is_relevant(contexts: list[dict], query: str = "") -> bool:
    """检索结果是否足以支撑回答（基于字符/词重叠，对中文友好）。

    - 无结果 -> 不相关
    - 有结果但与查询几乎无字符交集 -> 视为不相关，避免用不相关知识库内容强行作答
    - 与任一召回文档存在有效重叠 -> 相关
    """
    if not contexts:
        return False
    q_tokens = set(_TOKEN_RE.findall((query or "").lower()))
    if not q_tokens:
        # 无查询词可比对时，退化为「有结果即可」（避免误杀）
        return True
    for c in contexts[:3]:
        c_tokens = set(_TOKEN_RE.findall((c.get("text", "") or "").lower()))
        overlap = q_tokens & c_tokens
        # 中文按字重叠：≥1 个中文字相同即认为相关；英文按词重叠
        if overlap:
            # 要求覆盖查询中一定比例的中文单字，过滤巧合单字重叠；
            # 英文词（长度≥2）命中即认为相关
            ratio = len(overlap) / max(1, len(q_tokens))
            if ratio >= 0.3 or any(t in overlap for t in q_tokens if len(t) >= 2):
                return True
    return False


def safe_refuse(reason: str) -> str:
    return f"抱歉，我无法处理该请求（{reason}）。如有需要，请联系人工客服。"
