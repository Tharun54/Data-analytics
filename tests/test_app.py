import os
import tempfile

# Isolated DB and forced demo engine before the app is imported.
_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["CSE_DATABASE_URL"] = f"sqlite:///{_db.name}"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["CSE_SECRET_KEY"] = "test-secret-key-that-is-at-least-32-bytes-long"

import pytest
from fastapi.testclient import TestClient

from app.engine import demo, profiler
from app.engine.schema import validate_report
from app.main import app

CSV = b"""date,region,revenue,units
2026-01-05,North,1200,10
2026-01-20,South,800,7
2026-02-03,North,1500,12
2026-02-17,East,400,3
2026-03-02,South,950,8
2026-03-21,North,1700,14
"""


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


_n = 0


def signup(client, company="Acme"):
    global _n
    _n += 1
    r = client.post("/api/auth/signup", json={"email": f"u{_n}@example.com", "name": "U", "password": "password123", "company": company})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_signup_login_me(client):
    h = signup(client)
    me = client.get("/api/me", headers=h).json()
    assert me["org"]["plan"] == "free" and me["engine"] == "demo"
    assert client.post("/api/auth/login", json={"email": me["user"]["email"], "password": "password123"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": me["user"]["email"], "password": "wrong"}).status_code == 401
    assert client.get("/api/me").status_code == 401


def test_duplicate_signup(client):
    body = {"email": "dup@example.com", "name": "A", "password": "password123", "company": "X"}
    assert client.post("/api/auth/signup", json=body).status_code == 201
    assert client.post("/api/auth/signup", json=body).status_code == 409


def test_topic_analysis_to_dashboard(client):
    h = signup(client)
    a = client.post("/api/analyses", json={"topic": "Electric vehicles in India"}, headers=h).json()
    full = client.get(f"/api/analyses/{a['id']}", headers=h).json()  # background task ran synchronously in TestClient
    assert full["status"] == "done", full
    assert full["result"]["kpis"] and full["result"]["charts"]
    d = client.post(f"/api/analyses/{a['id']}/dashboard", headers=h).json()
    dash = client.get(f"/api/dashboards/{d['id']}", headers=h).json()
    kinds = {w["kind"] for w in dash["widgets"]}
    assert {"summary", "kpi", "chart", "insights"} <= kinds

    # remove all charts via PATCH
    keep = [{k: w[k] for k in ("analysis_id", "kind", "index")} for w in dash["widgets"] if w["kind"] != "chart"]
    dash = client.patch(f"/api/dashboards/{d['id']}", json={"widgets": keep}, headers=h).json()
    assert all(w["kind"] != "chart" for w in dash["widgets"])


def test_tenant_isolation(client):
    h1, h2 = signup(client, "One"), signup(client, "Two")
    a = client.post("/api/analyses", json={"topic": "Coffee prices"}, headers=h1).json()
    assert client.get(f"/api/analyses/{a['id']}", headers=h2).status_code == 404
    d = client.post(f"/api/analyses/{a['id']}/dashboard", headers=h1).json()
    assert client.get(f"/api/dashboards/{d['id']}", headers=h2).status_code == 404
    # cannot reference another org's analysis in your own dashboard
    r = client.post("/api/dashboards", json={"name": "x", "widgets": [{"analysis_id": a["id"], "kind": "summary"}]}, headers=h2)
    assert r.status_code == 422


def test_plan_limits_and_upgrade(client):
    h = signup(client)
    for i in range(5):
        assert client.post("/api/analyses", json={"topic": f"topic {i}"}, headers=h).status_code == 202
    assert client.post("/api/analyses", json={"topic": "one too many"}, headers=h).status_code == 402
    assert client.post("/api/billing/plan", json={"plan": "pro"}, headers=h).status_code == 200
    assert client.post("/api/analyses", json={"topic": "now allowed"}, headers=h).status_code == 202


def test_sharing_requires_paid_plan(client):
    h = signup(client)
    a = client.post("/api/analyses", json={"topic": "Remote work"}, headers=h).json()
    d = client.post(f"/api/analyses/{a['id']}/dashboard", headers=h).json()
    assert client.post(f"/api/dashboards/{d['id']}/share", headers=h).status_code == 402
    client.post("/api/billing/plan", json={"plan": "pro"}, headers=h)
    tok = client.post(f"/api/dashboards/{d['id']}/share", headers=h).json()["share_token"]
    pub = client.get(f"/api/public/dashboards/{tok}")
    assert pub.status_code == 200 and "share_token" not in pub.json()
    client.delete(f"/api/dashboards/{d['id']}/share", headers=h)
    assert client.get(f"/api/public/dashboards/{tok}").status_code == 404


def test_dataset_upload(client):
    h = signup(client)
    r = client.post("/api/datasets", headers=h, files={"file": ("sales.csv", CSV, "text/csv")},
                    data={"question": "Which region drives revenue?"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["dataset"]["rows"] == 6
    auto = client.get(f"/api/analyses/{body['analysis']['id']}", headers=h).json()
    titles = [c["title"] for c in auto["result"]["charts"]]
    assert any("over time" in t for t in titles) and any("by region" in t for t in titles)
    assert client.get(f"/api/analyses/{body['ai_analysis']['id']}", headers=h).json()["status"] == "done"


def test_bad_csv(client):
    h = signup(client)
    r = client.post("/api/datasets", headers=h, files={"file": ("x.csv", b"only_header\n", "text/csv")})
    assert r.status_code == 422


def test_unknown_api_route_is_404_not_spa(client):
    assert client.get("/api/nope").status_code == 404
    assert "CSE Plus" in client.get("/dashboards/whatever").text


def test_profiler_types():
    cols, rows = profiler.parse_csv(CSV)
    prof = profiler.profile(cols, rows)
    assert prof["date"]["type"] == "date"
    assert prof["revenue"]["type"] == "numeric" and prof["revenue"]["sum"] == 6550
    assert prof["region"]["type"] == "categorical"


def test_demo_is_deterministic_and_valid():
    assert demo.run_demo_analysis("abc") == demo.run_demo_analysis("abc")


def test_validate_drops_inconsistent_charts():
    r = demo.run_demo_analysis("x")
    r["charts"].append({"type": "bar", "title": "bad", "labels": ["a", "b"], "series": [{"name": "s", "data": [1]}], "insight": ""})
    assert all(c["title"] != "bad" for c in validate_report(r)["charts"])
