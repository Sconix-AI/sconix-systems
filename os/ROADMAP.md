# Sconix Systems — roadmap

See `STACK.md` for the locked stack. This is build order.

## Phase 0 — factory skeleton  (in progress, started 2026-08-30)

- [x] `~/systems/` tree, `STACK.md`, `ledger.md`, `inbox.md`
- [x] `sconixapp` package: `config`, `db`, `security`, `logging`, `health` — installs `--editable`, `task test` green
- [x] `sx` CLI: `doctor`, `new`, `ls`, `cap`, `ledger`
- [ ] `template-web` — Copier template -> deployable monorepo (`api/` + `web/` + `packages/`)
- [ ] `sx new demoapp` produces a repo where `task setup` + `task dev` work locally
- [ ] engine regression test (`~/systems/os && task test`)

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
