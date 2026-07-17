"""业务工具（原型用 mock 数据，接口预留真实 API 对接位）。

使用 LangChain 的 @tool 装饰器定义工具，契合 Agent 工具调用范式；
同时保留底层函数，供编排层直接调用。
"""
import re
import random

from langchain_core.tools import tool

_ORDER_DB = {}  # 运单/订单 mock 存储，首次查询时随机生成


def extract_order_id(text: str) -> str | None:
    """从文本中抽取订单号/物流单号（6 位以上数字，或 '单号' 后紧跟的数字）。"""
    m = re.search(r"(?:订单号|运单号|单号|订单|运单)[:：]?\s*([0-9]{6,})", text)
    if m:
        return m.group(1)
    m = re.search(r"\b([0-9]{6,})\b", text)
    return m.group(1) if m else None


def _ensure_order(order_id: str) -> dict:
    if order_id not in _ORDER_DB:
        statuses = ["待付款", "已付款", "已发货", "运输中", "已签收", "退货中"]
        items = ["无线蓝牙耳机", "智能手表", "机械键盘", "便携充电宝", "4K 显示器"]
        _ORDER_DB[order_id] = {
            "order_id": order_id,
            "status": random.choice(statuses),
            "item": random.choice(items),
            "amount": round(random.uniform(99, 1999), 2),
            "address": "上海市浦东新区xx路xx号",
        }
    return _ORDER_DB[order_id]


def query_order(order_id: str) -> dict:
    """查询订单信息。对接真实系统时替换为订单中心 API 调用。"""
    return _ensure_order(order_id)


def query_logistics(order_id: str) -> dict:
    """查询物流轨迹。对接真实系统时替换为物流商 API 调用。"""
    order = _ensure_order(order_id)
    steps = [
        {"time": "2026-07-15 10:22", "node": "商家已发货"},
        {"time": "2026-07-15 20:10", "node": "【杭州转运中心】已发出"},
        {"time": "2026-07-16 08:45", "node": "【上海分拨中心】到达"},
        {"time": "2026-07-16 14:30", "node": "快递员派送中，电话 138****0000"},
    ]
    return {"order_id": order_id, "status": order["status"], "tracking": steps}


def format_order(order_id: str) -> str:
    o = query_order(order_id)
    return (
        f"订单号 {o['order_id']} 的当前状态为「{o['status']}」：\n"
        f"- 商品：{o['item']}\n- 金额：¥{o['amount']}\n- 收货地址：{o['address']}"
    )


def format_logistics(order_id: str) -> str:
    l = query_logistics(order_id)
    lines = [f"订单号 {l['order_id']}（{l['status']}）物流轨迹："]
    for s in l["tracking"]:
        lines.append(f"  · {s['time']} {s['node']}")
    return "\n".join(lines)


# ---------------- LangChain 工具定义 ----------------

@tool
def order_query_tool(order_id: str) -> str:
    """根据订单号查询订单当前状态、商品、金额与收货地址。输入应为订单号字符串。"""
    return format_order(order_id)


@tool
def logistics_query_tool(order_id: str) -> str:
    """根据订单号查询物流轨迹。输入应为订单号字符串。"""
    return format_logistics(order_id)
