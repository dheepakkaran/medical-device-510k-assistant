"""API tests against the local database (skipped when Postgres is not running)."""
import pytest
from fastapi.testclient import TestClient

try:
    from app.db import connect
    connect().close()
    DB = True
except Exception:  # noqa: BLE001
    DB = False

pytestmark = pytest.mark.skipif(not DB, reason="needs Postgres with loaded data (scripts/db.sh start + ETL)")


@pytest.fixture(scope="module")
def client():
    from app.main import app
    return TestClient(app)


def test_health(client):
    j = client.get("/api/health").json()
    assert j["ok"] and j["devices"] > 0 and j["guidance_chunks"] > 0


def test_device_search_filters_by_product_code(client):
    rows = client.get("/api/devices", params={"product_code": "DQA", "limit": 5}).json()
    assert rows and all(r["product_code"] == "DQA" for r in rows)
    assert rows[0]["source"].endswith(rows[0]["k_number"])


def test_bad_product_code_rejected(client):
    assert client.get("/api/devices", params={"product_code": "DQA;drop"}).status_code == 422


def test_report_every_row_has_a_source(client):
    k = client.get("/api/devices", params={"product_code": "FRN", "limit": 1}).json()[0]["k_number"]
    md = client.get(f"/api/report/{k}").text
    rows = [l for l in md.splitlines() if l.startswith("| K") and not l.startswith("| K-number")]
    assert "DRAFT" in md and rows and all("accessdata.fda.gov" in r for r in rows)


def test_unknown_k_number_404(client):
    assert client.get("/api/report/K000000").status_code == 404
