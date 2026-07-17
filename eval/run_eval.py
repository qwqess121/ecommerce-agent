"""端到端评估：对测试集逐条调用 /chat，校验意图/转人工/检索命中，生成报告。"""
import json
import os
import httpx

BASE = "http://127.0.0.1:8000"
HERE = os.path.dirname(os.path.abspath(__file__))
CASE_FILE = os.path.join(HERE, "testset.json")
REPORT = os.path.join(HERE, "report.md")


def call(q: str) -> dict:
    r = httpx.post(f"{BASE}/chat", json={"session_id": "eval", "message": q}, timeout=60)
    return r.json()


def main():
    cases = json.load(open(CASE_FILE, encoding="utf-8"))
    rows, total, passed = [], len(cases), 0
    for c in cases:
        res = call(c["question"])
        intent = res["intent"]
        transfer = res["transfer"]
        ns = len(res["sources"])
        ok = intent == c.get("expect_intent")
        if "expect_transfer" in c:
            ok = ok and (transfer == c["expect_transfer"])
        passed += 1 if ok else 0
        rows.append({
            "id": c["id"], "question": c["question"], "expect": c.get("expect_intent"),
            "got": intent, "transfer": transfer, "src": ns,
            "answer": res["answer"][:60].replace("\n", " "), "ok": ok,
        })

    # 报告
    lines = ["# 评估报告", "", f"- 用例数：**{total}**  通过：**{passed}**  通过率：**{passed/total*100:.0f}%**", ""]
    lines.append("| # | 问题 | 期望意图 | 实际意图 | 转人工 | 引用数 | 结果 |")
    lines.append("|---|------|---------|---------|-------|-------|------|")
    for r in rows:
        lines.append(f"| {r['id']} | {r['question']} | {r['expect']} | {r['got']} | {'是' if r['transfer'] else '否'} | {r['src']} | {'✅' if r['ok'] else '❌'} |")
    lines += ["", "## 样例回答", ""]
    for r in rows:
        lines.append(f"- **Q{r['id']}**：{r['answer']}")
    open(REPORT, "w", encoding="utf-8").write("\n".join(lines))

    print(f"通过 {passed}/{total} ({passed/total*100:.0f}%)")
    for r in rows:
        flag = "OK " if r["ok"] else "FAIL"
        print(f"  [{flag}] #{r['id']} {r['question'][:30]} -> {r['got']} (transfer={r['transfer']}, src={r['src']})")
    print(f"报告已生成：{REPORT}")


if __name__ == "__main__":
    main()
