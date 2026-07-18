"""WHZ 电商客服智能体 —— 全面端到端自测脚本。

覆盖：健康检查、对话(知识/业务/闲聊/身份/转人工)、SSE 流式累积(验证多 delta 拼接完整)、
知识库增删改查、文件上传、前端资源可访问、会话重置。
测试结束后自动清理产生的运行时数据，保持环境干净。

用法：python tests/e2e_test.py
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(ROOT, "kb", "uploads")
USER_KB = os.path.join(ROOT, "kb", "user_entries.json")

results = []


def record(name, passed, detail=""):
    results.append((name, passed, detail))
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def post_json(path, obj):
    data = json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def get_json(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def get_status(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def get_text(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def sse_stream(path, obj):
    """读取 SSE 流，返回 (累积文本, meta 字典)。正确解析 event:/data: 块。

    后端事件格式：
      event: meta\\ndata: {...}\\n\\n
      event: delta\\ndata: "片段"\\n\\n
      event: done\\ndata: {}\\n\\n
    其中 delta 的 data 是 json.dumps(字符串)，解析后为 str；meta 的 data 是 JSON 对象。
    """
    body = json.dumps(obj)
    raw = ""
    try:
        out = subprocess.run(
            ["curl", "-s", "-N", "-m", "90", "-X", "POST", BASE + path,
             "-H", "Content-Type: application/json", "--data-binary", body],
            capture_output=True, text=True, timeout=120,
        )
        raw = out.stdout
    except Exception:
        req = urllib.request.Request(
            BASE + path, data=body.encode("utf-8"),
            headers={"Content-Type: application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read().decode("utf-8", errors="replace")
    streamed, meta = [], {}
    event = ""
    for block in raw.split("\n\n"):
        ev = ""
        data_parts = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                data_parts.append(line[5:].strip())
        if not data_parts:
            continue
        data_raw = "".join(data_parts)
        try:
            o = json.loads(data_raw)
        except Exception:
            o = data_raw  # 解析失败则保留原始字符串
        if ev == "meta":
            meta = o if isinstance(o, dict) else {}
        elif ev == "delta":
            if isinstance(o, str):
                streamed.append(o)
            elif isinstance(o, dict) and "text" in o:
                streamed.append(o["text"])
        # ev == "done" 忽略
    return "".join(streamed), meta


# ---------------- 1. 健康检查 ----------------
try:
    h = get_json("/health")
    ok = h.get("status") == "ok" and h.get("store", {}).get("chunks", 0) > 0
    record("健康检查 /health", ok, f"mock={h.get('mock')}, chunks={h.get('store',{}).get('chunks')}")
    BASE_CHUNKS = h.get("store", {}).get("chunks", 0)
except Exception as e:
    record("健康检查 /health", False, str(e))
    BASE_CHUNKS = 0

# ---------------- 2. 对话意图路由 ----------------
def check_intent(label, msg, expect_intent, expect_transfer=False):
    try:
        r = post_json("/chat", {"session_id": "t_" + label, "message": msg})
        intent = r.get("intent")
        transfer = r.get("transfer", False)
        ans = (r.get("answer") or "").strip()
        ok = (intent == expect_intent) and (len(ans) > 0)
        if expect_transfer:
            ok = ok and transfer
        detail = f"intent={intent}, transfer={transfer}, ans_len={len(ans)}"
        record(f"对话意图: {label}", ok, detail)
    except Exception as e:
        record(f"对话意图: {label}", False, str(e))

check_intent("知识问答", "如何申请退货？", "knowledge")
check_intent("业务查询", "查询订单 123456 的物流", "business")
check_intent("身份闲聊", "你叫什么", "chitchat")          # 验证之前的误判修复
check_intent("问候闲聊", "你好", "chitchat")
check_intent("转人工", "我要转人工", "human", expect_transfer=True)
check_intent("无关闲聊", "今天天气怎么样", "chitchat")

# ---------------- 3. SSE 流式累积 == 完整答案 + meta 意图一致 ----------------
def check_stream(label, msg):
    try:
        chat = post_json("/chat", {"session_id": "s_" + label, "message": msg})
        full = (chat.get("answer") or "").strip()
        expect_intent = chat.get("intent")
        streamed, meta = sse_stream("/chat/stream", {"session_id": "s_" + label, "message": msg})
        streamed = streamed.strip()
        ok = (streamed == full) and len(full) > 0 and (meta.get("intent") == expect_intent)
        detail = f"完整={len(full)}, 流式={len(streamed)}, meta.intent={meta.get('intent')}(期望 {expect_intent})"
        if not ok and len(full) > 0:
            detail += f" | 流式开头='{streamed[:20]}...' 完整开头='{full[:20]}...'"
        record(f"SSE 流式完整度+意图: {label}", ok, detail)
    except Exception as e:
        record(f"SSE 流式完整度+意图: {label}", False, str(e))

check_stream("知识问答", "如何申请退货？")
check_stream("业务查询", "查询订单 123456 的物流")
check_stream("身份闲聊", "你叫什么")


# ---------------- 3b. 多轮上下文（同一会话连续两轮） ----------------
def check_multiturn(label, msgs):
    try:
        sid = "mt_" + label
        answers = []
        for m in msgs:
            r = post_json("/chat", {"session_id": sid, "message": m})
            a = (r.get("answer") or "").strip()
            if not a:
                record(f"多轮上下文: {label}", False, f"第{m!r}轮返回空")
                return
            answers.append(a)
        # 第二轮应针对第二条消息作答，而非回显第一轮
        ok = len(answers) == len(msgs) and answers[1] != answers[0] and len(answers[1]) > 0
        record(f"多轮上下文: {label}", ok,
               f"轮1={len(answers[0])}字, 轮2={len(answers[1])}字, 轮2意图={post_json('/chat', {'session_id': sid, 'message': msgs[1]}).get('intent')}")
    except Exception as e:
        record(f"多轮上下文: {label}", False, str(e))

check_multiturn("订单后追问物流", ["查订单 123456", "它现在物流到哪了"])
check_multiturn("退货后问运费", ["如何申请退货？", "退货的运费谁出？"])

# ---------------- 4. 知识库列表 ----------------
try:
    e = get_json("/kb/entries")
    entries = e.get("entries", [])
    ok = isinstance(entries, list) and len(entries) > 0
    kinds = {}
    for x in entries:
        kinds[x.get("kind")] = kinds.get(x.get("kind"), 0) + 1
    record("知识库列表 /kb/entries", ok, f"条目数={len(entries)}, 类型分布={kinds}")
except Exception as ex:
    record("知识库列表 /kb/entries", False, str(ex))

# ---------------- 5. 知识库 新增 / 编辑 / 删除 往返 ----------------
TEST_TITLE = "[TEST] 会员权益政策"
TEST_HTML = "<p>会员可享受<b>专属折扣</b>，生日当月赠送<strong>双倍积分</strong>。</p>"
try:
    added = post_json("/kb/entries", {"title": TEST_TITLE, "html": TEST_HTML})
    eid = added.get("entry", {}).get("id")
    ok_add = added.get("ok") and bool(eid)
    # 验证 chunks 增加
    after_add = get_json("/kb_stats").get("chunks", 0)
    grew = after_add > BASE_CHUNKS
    record("知识库新增 /kb/entries(POST)", ok_add and grew,
           f"id={eid}, chunks {BASE_CHUNKS}->{after_add}")
except Exception as ex:
    record("知识库新增 /kb/entries(POST)", False, str(ex))
    eid = None

if eid:
    try:
        upd = post_json(f"/kb/entries/{eid}".replace("/kb/entries/", "/kb/entries/"), {})
    except Exception:
        upd = None
    try:
        # PUT 用 urllib 不支持，改用 requests 语义：用 http.client 发 PUT
        import http.client
        new_html = "<p>更新后：会员享受<strong>九折</strong>专属优惠。</p>"
        data = json.dumps({"title": TEST_TITLE + "(改)", "html": new_html}).encode()
        conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=30)
        conn.request("PUT", f"/kb/entries/{eid}", body=data,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        upd = json.loads(resp.read().decode())
        conn.close()
        new_title = upd.get("entry", {}).get("title", "")
        ok_upd = upd.get("ok") and TEST_TITLE + "(改)" in new_title
        record("知识库编辑 /kb/entries/{id}(PUT)", ok_upd, f"新标题='{new_title}'")
    except Exception as ex:
        record("知识库编辑 /kb/entries/{id}(PUT)", False, str(ex))

    try:
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=30)
        conn.request("DELETE", f"/kb/entries/{eid}")
        resp = conn.getresponse()
        dele = json.loads(resp.read().decode())
        conn.close()
        after_del = dele.get("stats", {}).get("chunks", -1)
        ok_del = dele.get("ok") and after_del == BASE_CHUNKS
        record("知识库删除 /kb/entries/{id}(DELETE)", ok_del,
               f"chunks 恢复为 {after_del} (基线 {BASE_CHUNKS})")
    except Exception as ex:
        record("知识库删除 /kb/entries/{id}(DELETE)", False, str(ex))

# ---------------- 6. 文件上传入库 ----------------
try:
    boundary = "----whztestboundary"
    content = "退货政策：商品签收后 7 天内可申请无理由退货，需保持吊牌完整。运费由商家承担。"
    head = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="file"; filename="test_return.txt"\r\n'
        f'Content-Type: text/plain\r\n\r\n'
    )
    tail = f'\r\n--{boundary}--\r\n'
    body = (head + content + tail).encode("utf-8")
    import http.client
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=60)
    conn.request("POST", "/kb/upload", body=body,
                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    resp = conn.getresponse()
    up = json.loads(resp.read().decode())
    conn.close()
    ok_up = up.get("ok") and "stats" in up
    record("文件上传 /kb/upload(POST multipart)", ok_up, f"file={up.get('file')}")
    # 上传后清理：删掉测试上传文件并重建
    try:
        for fn in os.listdir(UPLOAD_DIR):
            if fn.endswith("test_return.txt"):
                os.remove(os.path.join(UPLOAD_DIR, fn))
        post_json("/rebuild", {})
    except Exception:
        pass
except Exception as ex:
    record("文件上传 /kb/upload(POST multipart)", False, str(ex))

# ---------------- 7. 前端资源可访问 ----------------
try:
    html = get_text("/ui/")
    has_root = 'id="root"' in html
    m_js = re.search(r'src="(/ui/assets/[^"]+\.js)"', html)
    m_css = re.search(r'href="(/ui/assets/[^"]+\.css)"', html)
    js_ok = m_js and get_status(m_js.group(1)) == 200
    css_ok = m_css and get_status(m_css.group(1)) == 200
    record("前端页面 /ui/ 可访问", has_root and js_ok and css_ok,
           f"root={has_root}, js={m_js.group(1) if m_js else None}({get_status(m_js.group(1)) if m_js else '-'}), css={'OK' if css_ok else 'FAIL'}")
except Exception as ex:
    record("前端页面 /ui/ 可访问", False, str(ex))

# ---------------- 8. 会话重置 ----------------
try:
    r = post_json("/reset", {"session_id": "t_知识问答"})
    record("会话重置 /reset", r.get("ok") is True)
except Exception as ex:
    record("会话重置 /reset", False, str(ex))

# ---------------- 最终清理：删除所有 [TEST] 用户条目 ----------------
try:
    entries = get_json("/kb/entries").get("entries", [])
    import http.client
    for x in entries:
        if "[TEST]" in (x.get("title") or ""):
            conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=30)
            conn.request("DELETE", f"/kb/entries/{x['id']}")
            conn.getresponse().read()
            conn.close()
    # 清理上传文件 + 重建
    if os.path.isdir(UPLOAD_DIR):
        for fn in os.listdir(UPLOAD_DIR):
            if "test" in fn:
                try:
                    os.remove(os.path.join(UPLOAD_DIR, fn))
                except Exception:
                    pass
    post_json("/rebuild", {})
    # 清掉运行时用户条目文件，避免污染仓库
    if os.path.exists(USER_KB):
        try:
            os.remove(USER_KB)
        except Exception:
            pass
except Exception:
    pass

# ---------------- 汇总 ----------------
passed = sum(1 for _, p, _ in results if p)
total = len(results)
print("\n" + "=" * 56)
print(f"总计 {total} 项，通过 {passed} 项，失败 {total - passed} 项")
print("=" * 56)
sys.exit(0 if passed == total else 1)
