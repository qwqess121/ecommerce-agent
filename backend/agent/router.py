"""意图路由：知识问答 / 业务查询 / 闲聊 / 转人工。

以关键词启发式为主（可离线运行、便于测试）。业务查询触发条件：
包含物流类动词，或「含订单字样且有订单号」。避免把普通知识问答误判为业务。
"""
from backend.agent.tools import extract_order_id

LOGISTICS_VERB = [
    "物流", "快递", "运单", "发货", "配送", "寄送",
    "ship", "shipping", "deliver", "delivery",
]
HUMAN_KW = ["人工", "转人工", "客服人员", "真人", "human agent", "转接"]
GREET_KW = ["你好", "您好", "hi", "hello", "在吗", "在么", "哈喽"]
THANKS_KW = ["谢谢", "感谢", "thanks", "thank you", "多谢"]
# 电商主题词：命中则倾向走知识库；都不命中且非问候致谢，视为闲聊/无关
# 同时覆盖中英文，便于对开源英文语料做检索问答
ECOM_KW = [
    "订单", "物流", "快递", "退", "换", "货", "商品", "价格", "优惠", "券", "支付",
    "发票", "保修", "质保", "质量", "发货", "配送", "购买", "下单", "客服", "咨询",
    "分期", "积分", "会员", "地址", "签收", "破损", "售后", "维修", "秒杀", "预售",
    "包邮", "运费", "账户", "密码", "评价", "补偿", "索赔", "申领", "怎么", "如何",
    "什么", "为什么", "吗", "？", "?", "哪儿", "哪里", "哪", "能否", "可以", "是否",
    "成立", "公司",
    # 英文电商主题词
    "return", "refund", "exchange", "payment", "pay", "order", "invoice",
    "warranty", "shipping", "cancel", "coupon", "discount", "price", "product",
    "track", "how", "what", "why", "can", "do you", "method",
]


def classify(message: str) -> str:
    t = (message or "").lower()

    if any(k in t for k in HUMAN_KW):
        return "human"

    has_id = extract_order_id(message) is not None
    if any(v in t for v in LOGISTICS_VERB) or (("订单" in t or "order" in t) and has_id):
        return "business"

    if any(k in t for k in GREET_KW) or any(k in t for k in THANKS_KW):
        return "chitchat"

    # 含电商主题词 -> 知识问答；否则视为闲聊/无关，避免强行用知识库答非所问
    if any(k in t for k in ECOM_KW):
        return "knowledge"
    return "chitchat"
