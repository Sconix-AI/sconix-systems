# Sconix Systems — roadmap

See `STACK.md` for the locked stack. This is build order.

## Phase 0 — factory skeleton  (in progress, started 2026-08-30)

- [x] `~/systems/` tree, `STACK.md`, `ledger.md`, `inbox.md`
- [x] `sconixapp` package: `config`, `db`, `security`, `logging`, `health` — installs `--editable`, 7 tests green
- [x] `sx` CLI: `doctor`, `new`, `ls`, `cap`, `ledger`, `sync`, `gen`, `deploy` (stub)
- [x] `template-web` v0.1.0 (own git repo, tagged) -> `api/` (FastAPI + sconixapp + Alembic) + `web/` (Next 16 + Tailwind v4) + `packages/` (api-client, shared, tsconfig)
- [x] `sx new` verified end-to-end; `~/systems/os && task test` green (lib + copier-generate + uv sync + ruff + pytest)
- [x] SQLite path for zero-Docker local dev (db.py sqlite-aware, aiosqlite dep, `.env` default)
- [x] first Alembic migration generated from `models.py` (trim); web `pnpm install` + `next build` verified
- [ ] `task dev` full loop with Postgres — **blocked on Docker in WSL**
- [ ] install `sops` + `age` (substrate secrets — MISSING per `sx doctor`)

## Phase 1 — first real app: `trim` (link shortener)

- [x] `trim` built: FastAPI create/list/redirect + click count, Next 16 UI, prod compose + Caddy
- [x] `trim` API verified end-to-end locally (sqlite): create → 307 redirect → click count → stats
- [x] `sx provision user@host` + `sx deploy <app>` written (rsync → build → migrate → health-check; reads `deploy.env`)
- [ ] **user provides: a VPS (Hetzner/other) + SSH key + a domain** → then `sx provision` + `sx deploy trim`
- [ ] Docker available in WSL (only needed to *build/test images locally*; deploy builds on the box)
- [ ] stress test: `hey`/`wrk` against `https://<domain>/<code>`, watch `/api/stats` + `docker stats`
- [ ] push `sconix-systems` + `sconix-template-web` to GitHub (blocked: harness classifier — user runs `gh repo create`)

## Phase 1b — auth + billing (next app that needs them)

- [ ] `sconixapp.billing` — Stripe checkout + portal + webhook + entitlement gate
- [ ] `sconixapp.auth` wired: fastapi-users, Google OAuth, magic link, reset

## Phase 2 — harden

- [ ] `sconixapp`: `jobs` (arq), `email` (Resend), `ratelimit` (Redis), `admin` (bare)
- [ ] PostHog + Sentry wired into the template by default
- [ ] Nightly `pg_dump` -> R2/B2, restore drill documented
- [ ] `template-mobile` (Expo) — when an app needs it

## Deferred / never

See `STACK.md`.
