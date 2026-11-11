"""FastAPI backend: device search, cited guidance answers, draft predicate table."""
from datetime import date
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.db import connect
from app.retrieve import METHODS
from app import answer as ans

app = FastAPI(title="Medical Device 510(k) Research Assistant",
              description="Research aid over public FDA data. Not regulatory advice; a human checks every output.")
_conn = None
def conn():
    global _conn
    if _conn is None or _conn.closed:
        _conn = connect()
    return _conn

PMN = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID="
DEV_COLS = ["k_number", "device_name", "applicant", "product_code", "decision_date", "decision", "clearance_type"]


def _devices(rows):
    out = []
    for r in rows:
        d = dict(zip(DEV_COLS, r))
        d["decision_date"] = d["decision_date"].isoformat() if d["decision_date"] else None
        d["source"] = PMN + d["k_number"]
        out.append(d)
    return out


@app.get("/api/health")
def health():
    c = conn()
    return {"ok": True, "devices": c.execute("SELECT count(*) FROM devices").fetchone()[0],
            "guidance_chunks": c.execute("SELECT count(*) FROM guidance_chunks").fetchone()[0]}


@app.get("/api/devices")
def devices(q: str = Query("", max_length=100), product_code: str | None = Query(None, pattern="^[A-Za-z]{3}$"),
            limit: int = Query(20, ge=1, le=100)):
    sql = f"SELECT {','.join(DEV_COLS)} FROM devices WHERE (%s = '' OR device_name ILIKE %s OR applicant ILIKE %s)"
    args = [q, f"%{q}%", f"%{q}%"]
    if product_code:
        sql += " AND product_code = %s"; args.append(product_code.upper())
    sql += " ORDER BY decision_date DESC NULLS LAST LIMIT %s"; args.append(limit)
    return _devices(conn().execute(sql, args).fetchall())


@app.get("/api/devices/{k_number}")
def device(k_number: str):
    rows = conn().execute(f"SELECT {','.join(DEV_COLS)} FROM devices WHERE k_number=%s", (k_number.upper(),)).fetchall()
    if not rows:
        raise HTTPException(404, "K-number not in the local database")
    return _devices(rows)[0]


class AskIn(BaseModel):
    question: str = Field(min_length=5, max_length=400)
    method: str = Field("hybrid", pattern="^(keyword|vector|hybrid)$")


@app.post("/api/ask")
def ask(body: AskIn):
    passages = METHODS[body.method](conn(), body.question, 5)
    try:
        result = ans.answer(body.question, passages, tag="api")
    except RuntimeError as e:          # budget reached or no API key: still return the cited passages
        result = {"found": False, "answer": "", "citations": [], "verified": False, "route": [], "note": str(e)}
    except Exception as e:  # noqa: BLE001  - LLM unavailable; passages alone stay useful
        result = {"found": False, "answer": "", "citations": [], "verified": False, "route": [],
                  "note": f"LLM unavailable ({type(e).__name__}); showing passages only"}
    result["passages"] = [{k: p[k] for k in ("id", "doc_id", "doc_title", "page", "text")} for p in passages]
    return result


@app.get("/api/report/{k_number}", response_class=PlainTextResponse)
def report(k_number: str, n: int = Query(5, ge=1, le=20)):
    """Draft predicate comparison table: earlier clearances with the same product code. Every row links its source."""
    subj = device(k_number)
    rows = conn().execute(
        f"SELECT {','.join(DEV_COLS)} FROM devices WHERE product_code=%s AND k_number<>%s "
        "AND decision_date < %s ORDER BY decision_date DESC LIMIT %s",
        (subj["product_code"], subj["k_number"], subj["decision_date"] or date.today().isoformat(), n)).fetchall()
    lines = [f"# Draft predicate comparison: {subj['k_number']} ({subj['device_name']})", "",
             f"Product code **{subj['product_code']}** · subject cleared {subj['decision_date']} · source: {subj['source']}", "",
             "> DRAFT for a regulatory reviewer. Candidate predicates = earlier clearances with the same product code (openFDA). "
             "A human must confirm intended use and technological characteristics before any use.", "",
             "| K-number | Device | Applicant | Cleared | Decision | Source |", "|---|---|---|---|---|---|"]
    cell = lambda v: str(v or "").replace("|", "/")  # keep the markdown table intact
    for d in _devices(rows):
        lines.append("| " + " | ".join(cell(d[k]) for k in ("k_number", "device_name", "applicant", "decision_date", "decision", "source")) + " |")
    lines += ["", f"Generated {date.today().isoformat()} from openFDA device/510k data loaded by etl/devices.py."]
    return "\n".join(lines)


_web = Path(__file__).resolve().parent.parent / "web" / "dist"
if _web.exists():
    app.mount("/", StaticFiles(directory=_web, html=True), name="web")
