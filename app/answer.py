"""Cited answers with model routing (cascade):
  1. Claude Haiku 5.5 (cheap) drafts an answer as JSON with quotes.
  2. app/cite.py checks every quote word for word against the cited passage.
  3. Only if the check fails, Claude Opus 5.5 (strong) answers once more.
  4. If Opus also fails, return the passages with no answer (never an unverified quote).
Every call is written to results/cost_ledger.jsonl. A hard budget stops calls past BUDGET_USD."""
import json, os, time
from pathlib import Path
import anthropic
from dotenv import load_dotenv

from app.cite import check

load_dotenv()
CHEAP, STRONG = "claude-haiku-5-5", "claude-opus-5-5"
PRICE = {CHEAP: (0.10, 0.50), STRONG: (4.00, 20.00)}  # $ per 1M input / output tokens
BUDGET_USD = float(os.getenv("BUDGET_USD", "0.30"))
LEDGER = Path(os.getenv("LEDGER", "results/cost_ledger.jsonl"))
SYSTEM = Path(__file__).resolve().parent.parent.joinpath("prompts/answer_v1.txt").read_text()
SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": {
            "type": "object",
            "properties": {"passage_id": {"type": "integer"}, "quote": {"type": "string"}},
            "required": ["passage_id", "quote"], "additionalProperties": False}},
    },
    "required": ["found", "answer", "citations"], "additionalProperties": False,
}

_client = None
def client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def spent() -> float:
    if not LEDGER.exists():
        return 0.0
    return sum(json.loads(l)["cost_usd"] for l in LEDGER.read_text().splitlines() if l.strip())


def _context(passages: list[dict]) -> str:
    # compact context: only id, short title, page, text (no embeddings, no metadata the model doesn't need)
    return "\n\n".join(f"[passage {p['id']}] {p['doc_title']} | page {p['page']}\n{p['text']}" for p in passages)


def _call(model: str, question: str, passages: list[dict], tag: str) -> dict:
    if spent() >= BUDGET_USD:
        raise RuntimeError(f"budget ${BUDGET_USD} reached")
    kwargs = dict(
        model=model, max_tokens=2000,
        system=SYSTEM,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": f"Passages:\n{_context(passages)}\n\nQuestion: {question}"}],
    )
    if model == STRONG:  # server-side refusal fallback on the strong model
        kwargs.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    t0 = time.time()
    resp = client().beta.messages.create(**kwargs)
    u = resp.usage
    cost = (u.input_tokens * PRICE[model][0] + u.output_tokens * PRICE[model][1]) / 1e6
    LEDGER.parent.mkdir(exist_ok=True)
    with LEDGER.open("a") as f:
        f.write(json.dumps({"tag": tag, "model": model, "in": u.input_tokens, "out": u.output_tokens,
                            "cost_usd": round(cost, 6), "secs": round(time.time() - t0, 2),
                            "stop": resp.stop_reason}) + "\n")
    if resp.stop_reason in ("refusal", "max_tokens"):
        return {"found": False, "answer": "", "citations": [], "_stop": resp.stop_reason}
    text = "".join(b.text for b in resp.content if b.type == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"found": False, "answer": "", "citations": [], "_stop": "bad_json"}


def answer(question: str, passages: list[dict], tag: str = "ask", route: str = "cascade") -> dict:
    by_id = {p["id"]: p for p in passages}
    first = STRONG if route == "strong_only" else CHEAP
    res = _call(first, question, passages, tag)
    ok, probs = check(res, by_id)
    trail = [{"model": first, "verified": ok, "problems": probs}]
    if not ok and route == "cascade":
        res = _call(STRONG, question, passages, tag + ":escalated")
        ok, probs = check(res, by_id)
        trail.append({"model": STRONG, "verified": ok, "problems": probs})
    if not ok:
        res = {"found": False, "answer": "", "citations": []}
    for c in res.get("citations", []):
        p = by_id[c["passage_id"]]
        c.update(doc_id=p["doc_id"], doc_title=p["doc_title"], page=p["page"])
    return {**{k: res[k] for k in ("found", "answer", "citations")}, "verified": ok, "route": trail}
