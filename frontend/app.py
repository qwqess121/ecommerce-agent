"""Gradio 前端：聊天 + 知识库管理（调用后端 FastAPI）。"""
import httpx
import gradio as gr

from backend.config import HOST, PORT

BASE = f"http://{HOST}:{PORT}"


def chat_fn(message, history, session_id):
    try:
        r = httpx.post(f"{BASE}/chat", json={"session_id": session_id, "message": message}, timeout=60)
        data = r.json()
    except Exception as e:
        return history + [{"role": "user", "content": message}, {"role": "assistant", "content": f"调用后端失败：{e}"}], "（后端未启动？）", ""
    answer = data["answer"]
    sources = data.get("sources", [])
    intent = data.get("intent")
    transfer = data.get("transfer")
    src_text = "\n".join(f"· {s['source']}：{s['snippet']}" for s in sources) or "（无引用）"
    tag = f"\n\n[意图: {intent}" + ("，已转人工]" if transfer else "]")
    new_history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": answer + tag},
    ]
    return new_history, src_text, ""


def reset_fn(session_id):
    try:
        httpx.post(f"{BASE}/reset", json={"session_id": session_id}, timeout=30)
    except Exception:
        pass
    return [], "已清空对话"


def rebuild_fn():
    try:
        r = httpx.post(f"{BASE}/rebuild", timeout=120)
        return f"重建完成：{r.json()}"
    except Exception as e:
        return f"重建失败：{e}"


def upload_fn(file, session_id):
    if file is None:
        return "请先选择文件"
    try:
        with open(file.name, "rb") as f:
            r = httpx.post(f"{BASE}/ingest", files={"file": (file.name, f, "application/octet-stream")}, timeout=120)
        return f"上传并建立索引完成：{r.json()}"
    except Exception as e:
        return f"上传失败：{e}"


def launch():
    with gr.Blocks(title="电商客服智能体") as demo:
        gr.Markdown("# 电商客服智能体（RAG + Agent）")
        session_id = gr.State("demo-session")
        with gr.Tabs():
            with gr.Tab("聊天"):
                chatbot = gr.Chatbot(height=420, label="对话")
                msg = gr.Textbox(placeholder="例如：How can I return a product?  /  查询订单 123456  /  转人工")
                with gr.Row():
                    send = gr.Button("发送", variant="primary")
                    clr = gr.Button("清空对话")
                srcbox = gr.Textbox(label="参考来源", lines=4, interactive=False)
                send.click(chat_fn, [msg, chatbot, session_id], [chatbot, srcbox, msg])
                msg.submit(chat_fn, [msg, chatbot, session_id], [chatbot, srcbox, msg])
                clr.click(reset_fn, [session_id], [chatbot, srcbox])
            with gr.Tab("知识库管理"):
                gr.Markdown("支持上传 JSON / JSONL / TXT / MD / CSV，上传后自动重建索引。也可点击「重建知识库」扫描 kb/ 下全部文件。")
                up = gr.File(label="选择知识文件")
                up_btn = gr.Button("上传并建立索引", variant="primary")
                up_out = gr.Textbox(label="结果", lines=4, interactive=False)
                up_btn.click(upload_fn, [up, session_id], [up_out])
                rb = gr.Button("重建知识库（扫描 kb/ 全部文件）")
                rb.click(rebuild_fn, [], [up_out])
    demo.launch(server_name=HOST, server_port=7860, share=False)


if __name__ == "__main__":
    launch()
