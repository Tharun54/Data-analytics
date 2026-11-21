# CSE Plus — business plan (one page)

**Positioning:** "An analyst on demand." Ask about any topic, get a sourced, board-ready analysis and a
live dashboard in minutes instead of a two-week consultant engagement.

**Customers (start narrow):**
1. Founders & strategy teams doing market sizing / competitor scans
2. Consultants and agencies producing client research decks
3. Students and researchers (Free tier → word of mouth)

**Revenue:** Free → Pro $49 → Business $299 per workspace / month, plus overage packs.
Custom research (human analyst review on top of AI output) as a high-margin services add-on.

**Unit economics (check with real usage):** cost per AI analysis = tokens + web searches. Log
`usage` per run (already done) for the first 100 analyses, then set prices so the Pro plan's
100 analyses cost < 25% of $49. Levers: `CSE_EFFORT=low` for Free, fewer `max_uses` web searches,
prompt caching, Batch API for scheduled refreshes.

**Moat over time:** saved topic history + scheduled refresh (trend data no one else has for that
customer), dataset connectors, team workflows, and a library of verified sources per industry.

**90-day plan:**
- Weeks 1–4: Stripe, Postgres, job queue, deploy (Render/Fly/Railway); 10 design-partner users
- Weeks 5–8: scheduled refresh, PDF export; landing page + 20 public sample dashboards for SEO
- Weeks 9–12: launch (Product Hunt, LinkedIn, student communities); target 30 paying workspaces
