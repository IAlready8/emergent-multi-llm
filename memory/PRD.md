# Prometheus — Product Requirements Document

## Original Problem Statement
Multi-Agent Orchestration Platform. Users upload documents, connect data sources, or configure custom agent workflows; a fleet of 5 AI agents (Analyzer, Aggregator, AnomalyDetector, Classifier, Synthesizer) processes them via OpenAI GPT-5.2 and Google Gemini with real-time SSE streaming. Includes email/password + Google auth, Stripe subscriptions (Free/Pro/Enterprise), GDPR compliance, JSON+PDF export, admin dashboard.

## User Personas
- **Data / ops teams**: quick document + dataset analysis
- **Analysts**: anomaly detection and classification pipelines
- **Power users**: custom multi-agent workflow builder

## Architecture
- **Backend**: FastAPI (Python), MongoDB via motor, JWT + Emergent Google session cookies, SSE via async RunBus, WeasyPrint HTML→PDF, Stripe subscriptions (claimable sandbox), Resend emails, emergentintegrations LLM streaming.
- **Frontend**: React 19 + React Router 7 + Tailwind + shadcn/ui + sonner + lucide-react. AuthContext, axios interceptor w/ refresh token rotation, EventSource for streaming.
- **Tiers**: config-driven in `backend/config.py` (`TIERS`), Stripe lookup_keys: pro_monthly / pro_annual / enterprise_monthly / enterprise_annual.

## What's Been Implemented (2026-02)
- Auth: signup, login, refresh, /me, logout, password reset (Resend), Emergent Google Auth.
- Runs: create, list w/ filters + tier history window, get, delete, SSE stream (`?token=` fallback for EventSource), JSON + PDF export.
- Agents: 5 types (Analyzer/Aggregator/AnomalyDetector/Classifier/Synthesizer), sequential chaining, retry w/ exponential backoff, per-agent timeout, per-run timeout, provider abstraction (GPT-5.2 + Gemini 3 flash).
- Templates: doc_insight, csv_anomaly, url_research. Custom workflow builder (Pro/Enterprise).
- Uploads: CSV/TXT/MD/JSON with tier-based size + row limits, MIME check.
- URL fetch: SSRF-protected (private IPs blocked), HTML stripped, size-capped.
- Quotas: per-tier run limit, hourly rate limit, custom-workflows gating, agent whitelist.
- Billing: Stripe Checkout w/ SMP managed_payments (US SaaS), webhook /api/stripe/webhook (subscription lifecycle), billing portal, plan status.
- GDPR: full export (JSON), account deletion with cascading cleanup.
- Admin: overview (users/runs/revenue/feedback), Prometheus metrics endpoint.
- Security: OWASP headers middleware, CORS, per-user rate limiter, bcrypt passwords.
- Seeded admin: admin@prometheus.ai / AdminPass123! (enterprise tier).

## Deferred / Backlog
### P1
- Postgres + S3 read-only connectors (Enterprise, feature-flag).
- Interactive React Flow DAG (currently a linear list on RunView — good UX but not the drag-drop node graph).
- Workflow re-run + clone from history.
- PDF GridFS storage & signed download links (currently PDFs generated on-demand, not persisted).

### P2
- Payment failure 3-day grace period with read-only account UI banner.
- Downgrade at period end (currently upgrade only via checkout).
- Admin: disable user, grant manual credits UI.
- Full Prometheus metrics (queue depth, provider error rates, avg agent duration).
- Multi-URL fetch per run; CSV header mapping UI.

## Next Task List (post-1st-finish)
1. Build interactive @xyflow/react DAG builder for /app/workflows.
2. Persist generated PDFs in GridFS with per-run linkage + signed URLs.
3. Add downgrade + cancel scheduled changes flow via Stripe portal integration.
4. Add Postgres/S3 connector CRUD + safe query executor.
