"""Answer eval (run once): cascade on the 20 frozen questions + 3 out-of-scope questions;
ablation = strong model only on q01-q10 (subset fixed before the run to stay under the $0.30 budget).
Passages come from the app default retriever (hybrid, top 5)."""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.db import connect
from app.retrieve import hybrid
from app.answer import answer

QF = Path("eval/questions.jsonl")
assert hashlib.sha256(QF.read_bytes()).hexdigest() == Path("eval/questions.sha256").read_text().split()[0]
qs = [json.loads(l) for l in QF.read_text().splitlines()]
negs = [json.loads(l) for l in Path("eval/negatives.jsonl").read_text().splitlines()]
conn = connect()
LEDGER = Path("results/cost_ledger.jsonl")


def ledger_cost(prefix):
    rows = [json.loads(l) for l in LEDGER.read_text().splitlines()] if LEDGER.exists() else []
    return round(sum(r["cost_usd"] for r in rows if r["tag"].startswith(prefix)), 4)


def run(arm, items, route):
    out = []
    for q in items:
        ps = hybrid(conn, q["question"], 5)
        r = answer(q["question"], ps, tag=f"{arm}:{q['id']}", route=route)
        gold = {tuple(g) for g in q.get("gold", [])}
        cited = {(c["doc_id"], c["page"]) for c in r["citations"]}
        retrieved_gold = any((p["doc_id"], p["page"]) in gold for p in ps)
        out.append({"id": q["id"], "found": r["found"], "verified": r["verified"],
                    "escalated": len(r["route"]) > 1, "retrieved_gold": retrieved_gold,
                    "cites_gold_page": bool(cited & gold), "answer": r["answer"], "citations": r["citations"]})
    return out


def summary(rows, arm):
    n = len(rows)
    return {"n": n, "answered": sum(r["found"] for r in rows),
            "all_quotes_verified": sum(r["verified"] for r in rows),
            "cites_gold_page": sum(r["cites_gold_page"] for r in rows),
            "gold_page_retrieved": sum(r["retrieved_gold"] for r in rows),
            "escalated_to_strong": sum(r["escalated"] for r in rows), "cost_usd": ledger_cost(arm)}

res = {}
res["cascade_test20"] = run("cascade", qs, "cascade")
res["cascade_negatives"] = run("negcascade", negs, "cascade")
res["strong_only_q01_q10"] = run("strong", qs[:10], "strong_only")
cascade10 = [r for r in res["cascade_test20"] if r["id"] in {q["id"] for q in qs[:10]}]
summ = {"cascade_test20": summary(res["cascade_test20"], "cascade"),
        "cascade_negatives": summary(res["cascade_negatives"], "negcascade"),
        "strong_only_q01_q10": summary(res["strong_only_q01_q10"], "strong"),
        "cascade_q01_q10": {k: v for k, v in summary(cascade10, "cascade:q0").items()}}
# cascade cost on q01-q10 only (q01..q09 prefix + q10)
summ["cascade_q01_q10"]["cost_usd"] = round(ledger_cost("cascade:q0") + ledger_cost("cascade:q10"), 4)
Path("results/answers.json").write_text(json.dumps({"summary": summ, "rows": res}, indent=2))
print(json.dumps(summ, indent=1))
