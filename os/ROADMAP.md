# Sconix Systems — roadmap

See `STACK.md` for the locked stack. This is build order.

## Phase 0 — factory skeleton  (in progress, started 2026-08-30)

- [x] `~/systems/` tree, `STACK.md`, `ledger.md`, `inbox.md`
- [x] `sconixapp` package: `config`, `db`, `security`, `logging`, `health` — installs `--editable`, 7 tests green
- [x] `sx` CLI: `doctor`, `new`, `ls`, `cap`, `ledger`, `sync`, `gen`, `deploy` (stub)
- [x] `template-web` v0.1.0 (own git repo, tagged) -> `api/` (FastAPI + sconixapp + Alembic) + `web/` (Next 16 + Tailwind v4) + `packages/` (api-client, shared, tsconfig)
- [x] `sx new` verified end-to-end; `~/systems/os && task test` green (lib + copier-generate + uv sync + ruff + pytest)
- [ ] `task dev` / `task setup` fully exercised locally — **blocked on Docker in WSL** (postgres/redis containers)
- [ ] install `sops` + `age` (substrate secrets — currently MISSING per `sx doctor`)
- [ ] first Alembic migration generated from `models.py`; web `pnpm install` + `next build` verified

## Phase 1 — first real app

- [ ] Docker available in WSL (Docker Desktop integration or engine in WSL)
- [ ] Provision the Hetzner box: Docker, Caddy, GHCR auth, `deploy` user, ufw
- [ ] `sx deploy` — build images in CI, push to GHCR, SSH + `compose up -d`
- [ ] `sconixapp.billing` — Stripe checkout + customer portal + webhook + entitlement gate
- [ ] `sconixapp.auth` wired: fastapi-users, Google OAuth, magic link, reset
- [ ] Generate app #1, ship landing + waitlist

## Phase 2 — harden

- [ ] `sconixapp`: `jobs` (arq), `email` (Resend), `ratelimit` (Redis), `admin` (bare)
- [ ] PostHog + Sentry wired into the template by default
- [ ] Nightly `pg_dump` -> R2/B2, restore drill documented
- [ ] `template-mobile` (Expo) — when an app needs it

## Deferred / never

See `STACK.md`.
