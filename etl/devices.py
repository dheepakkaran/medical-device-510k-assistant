"""ETL: openFDA 510(k) clearances for 5 product codes -> clean -> PostgreSQL `devices`.

Extract: api.fda.gov/device/510k.json (public, no key; paged 1000 at a time)
Transform: keep needed fields, parse dates, drop rows without k_number/device_name, dedupe on k_number
Load: upsert into devices; counts written to results/etl_log.json
"""
import json, sys, time
from datetime import date
from pathlib import Path
import httpx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.db import connect, init_schema

PRODUCT_CODES = {
    "DQA": "pulse oximeter",
    "NBW": "blood glucose meter (over the counter)",
    "FRN": "infusion pump",
    "DXN": "non-invasive blood pressure system",
    "DRX": "ECG electrode",
}
URL = "https://api.fda.gov/device/510k.json"
FIELDS = ["k_number", "device_name", "applicant", "product_code", "decision_date",
          "decision_description", "clearance_type", "advisory_committee_description"]


def extract(code: str) -> list[dict]:
    rows, skip = [], 0
    with httpx.Client(timeout=60) as c:
        while True:
            r = c.get(URL, params={"search": f"product_code:{code}", "limit": 1000, "skip": skip})
            if r.status_code == 404:  # openFDA returns 404 when no more results
                break
            r.raise_for_status()
            batch = r.json()["results"]
            rows += batch
            if len(batch) < 1000:
                break
            skip += 1000
            time.sleep(0.3)
    return rows


def transform(raw: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame([{f: r.get(f) for f in FIELDS} for r in raw])
    if df.empty:
        return df
    df = df.rename(columns={"decision_description": "decision",
                            "advisory_committee_description": "advisory_committee"})
    for col in ["device_name", "applicant", "decision", "clearance_type", "advisory_committee"]:
        df[col] = df[col].astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
    df["product_code"] = df["product_code"].astype("string").str.strip().str.upper()
    df["decision_date"] = pd.to_datetime(df["decision_date"], errors="coerce").dt.date
    df = df[df["k_number"].notna() & df["device_name"].notna() & (df["device_name"] != "")]
    df = df.drop_duplicates(subset="k_number", keep="first")
    return df


def load(conn, df: pd.DataFrame) -> int:
    cols = ["k_number", "device_name", "applicant", "product_code", "decision_date",
            "decision", "clearance_type", "advisory_committee"]
    recs = [tuple(None if pd.isna(v) else v for v in row) for row in df[cols].itertuples(index=False)]
    with conn.cursor() as cur:
        cur.executemany(
            f"INSERT INTO devices ({','.join(cols)}) VALUES ({','.join(['%s']*len(cols))}) "
            "ON CONFLICT (k_number) DO UPDATE SET device_name=EXCLUDED.device_name, decision=EXCLUDED.decision",
            recs)
    return len(recs)


def main():
    conn = connect(); init_schema(conn)
    log = {"run_date": date.today().isoformat(), "source": URL, "codes": {}}
    for code, name in PRODUCT_CODES.items():
        raw = extract(code)
        df = transform(raw)
        n = load(conn, df)
        log["codes"][code] = {"name": name, "rows_in": len(raw), "rows_dropped": len(raw) - len(df), "rows_loaded": n}
        print(code, log["codes"][code])
    log["total_loaded"] = conn.execute("SELECT count(*) FROM devices").fetchone()[0]
    Path("results").mkdir(exist_ok=True)
    Path("results/etl_log.json").write_text(json.dumps(log, indent=2))
    print("total in devices:", log["total_loaded"])


if __name__ == "__main__":
    main()
