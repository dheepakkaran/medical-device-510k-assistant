"""Score keyword vs vector vs hybrid on the frozen 20 questions: hit@1, hit@3, hit@5 (doc + page match)."""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.db import connect
from app.retrieve import METHODS

QF = Path("eval/questions.jsonl")
assert hashlib.sha256(QF.read_bytes()).hexdigest() == Path("eval/questions.sha256").read_text().split()[0], "questions changed"
qs = [json.loads(l) for l in QF.read_text().splitlines()]
conn = connect()
out = {"n": len(qs), "methods": {}, "per_question": []}
hits = {m: {1: 0, 3: 0, 5: 0} for m in METHODS}
for q in qs:
    gold = {tuple(g) for g in q["gold"]}
    row = {"id": q["id"]}
    for m, fn in METHODS.items():
        got = [(r["doc_id"], r["page"]) for r in fn(conn, q["question"], 5)]
        first = next((i + 1 for i, g in enumerate(got) if g in gold), None)
        row[m] = first
        for k in (1, 3, 5):
            hits[m][k] += bool(first and first <= k)
    out["per_question"].append(row)
for m in METHODS:
    out["methods"][m] = {f"hit@{k}": hits[m][k] for k in (1, 3, 5)}
Path("results/retrieval.json").write_text(json.dumps(out, indent=2))
for m, v in out["methods"].items():
    print(f"{m:8s}", "  ".join(f"{k} {n}/{len(qs)}" for k, n in v.items()))
