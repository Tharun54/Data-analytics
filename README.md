# CSE Plus

**Analysis on any topic, delivered as live dashboards.** A multi-tenant SaaS: a customer types a topic
(a market, company, technology, trend, policy…) or uploads a CSV, and CSE Plus returns an executive
analysis — KPIs, charts, insights, SWOT, recommendations, sources — and turns it into a dedicated,
shareable dashboard in one click.

## Quick start

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add ANTHROPIC_API_KEY for live AI research; leave empty for demo mode
uvicorn app.main:app --reload
```

Open http://localhost:8000, create a workspace, and analyse a topic. API docs: http://localhost:8000/docs

Run the tests: `pytest -q`

Docker: `docker build -t cseplus . && docker run -p 8000:8000 --env-file .env -v cse-data:/data cseplus`

## How it works

| Piece | What it does | Where |
|---|---|---|
| **AI research engine** | One Claude request per analysis: live web search (paid plans) + adaptive thinking, output constrained by JSON Schema to the report contract so it renders straight into charts. Server-side refusal fallback enabled. | `app/engine/ai.py` |
| **Report contract** | Single JSON shape every engine returns (KPIs, charts, insights, SWOT, recs, sources, confidence). Validator drops inconsistent charts so the UI never breaks. | `app/engine/schema.py` |
| **Demo engine** | Deterministic synthetic report when no API key is set — the whole product runs offline. | `app/engine/demo.py` |
| **CSV profiler** | Type inference, stats, time-series / category / distribution charts, data-quality and correlation insights. Optional AI question grounded on the profile + a 25-row sample (not the raw file — cheap and private). | `app/engine/profiler.py` |
| **Dashboards** | Widgets reference analysis parts (`kpi`, `chart`, `summary`, `insights`, `swot`, `recommendations`); editable, public share links on paid plans. | `app/routers/dashboards.py` |
| **SaaS layer** | Workspaces (orgs), JWT auth, bcrypt, plan catalogue, monthly usage metering + limits (HTTP 402 on overage), strict tenant isolation. | `app/plans.py`, `app/security.py` |
| **Web app** | No-build SPA, Chart.js (vendored), light/dark, colour-blind-safe palette, chart ⇄ table toggle, mobile-ready. | `app/static/` |

## Plans

| | Free | Pro ($49/mo) | Business ($299/mo) |
|---|---|---|---|
| Analyses / month | 5 | 100 | 1,000 |
| CSV uploads / month | 3 | 50 | 500 |
| Dashboards | 2 | 25 | Unlimited |
| Live web research + sources | – | ✓ | ✓ |
| Public dashboard links | – | ✓ | ✓ |

Edit `app/plans.py` to change pricing/limits.

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | – | Empty ⇒ demo engine |
| `CSE_MODEL` | `claude-opus-5-5` | |
| `CSE_EFFORT` | `medium` | `low` is cheaper/faster, `high` researches deeper |
| `CSE_WEB_SEARCH` | `true` | Global kill switch for web research |
| `CSE_SECRET_KEY` | random per boot | **Set in production** or all sessions reset on restart |
| `CSE_DATABASE_URL` | `sqlite:///./cseplus.db` | Use Postgres in production |

See `docs/ROADMAP.md` for the path to production and `docs/BUSINESS_PLAN.md` for the go-to-market plan.
