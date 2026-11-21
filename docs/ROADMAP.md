# Roadmap — MVP to production

## Done (v0.1)
- Topic → AI analysis → dashboard; CSV → profiled dashboard (+ optional AI question)
- Workspaces, auth, plans, usage metering, limits, public share links
- Demo mode, tests, Docker image

## Before charging customers (launch blockers)
1. **Payments** — Stripe Checkout + Customer Portal. Replace `POST /api/billing/plan` with a Stripe
   webhook (`checkout.session.completed`, `customer.subscription.updated/deleted`) that sets `org.plan`.
   Until then that endpoint lets any workspace owner self-upgrade.
2. **Postgres + migrations** (Alembic). SQLite is fine for a pilot only.
3. **Job queue** — move analyses from FastAPI `BackgroundTasks` to a worker (RQ/Celery/Arq + Redis) so
   restarts don't drop in-flight jobs and you can scale workers separately. Mark stale `running` jobs failed on boot.
4. **Auth hardening** — email verification, password reset, login rate limiting, httpOnly cookie sessions
   instead of localStorage tokens, team invites (`role=member`).
5. **Ops** — HTTPS, error tracking (Sentry), structured logs, backups, per-analysis token/cost logging
   (usage is already logged by `app/engine/ai.py`).
6. **Legal** — Terms, Privacy Policy, DPA; disclaimer that AI analysis is not financial/legal advice.

## Next features
- Scheduled refresh: re-run a topic weekly and show change-over-time on the dashboard
- Drag-and-drop dashboard layout; mix widgets from several analyses
- PDF / PPTX export of dashboards; white-label reports for Business plan
- Connectors: Google Sheets, Postgres, BigQuery, Shopify, GA4
- Chat with a dashboard ("why did X drop?") grounded on the analysis + dataset
- Team workspaces, SSO (Business), audit log
- Prompt caching of the system prompt and Batch API for bulk/scheduled runs (50% cost)
