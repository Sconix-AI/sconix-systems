# Sconix Systems — Phase 1 build plan

Created 2026-08-30. Expands ROADMAP.md Phase 1b/2. Terse on purpose; see STACK.md for the locked stack.

## The bet

Factory-first. Two products, sequenced so the money loop is proven on the small one:

1. **App #1 — Relnotes** (changelog / release-notes generator). Small, single-job, sticky, low agent cost. Its job is to prove `sx deploy` + `sconixapp.billing` with a real paying customer.
2. **App #2 — Skillforge** (agentic technical skill-builder). Bigger. Ships free + waitlist, dogfooded from `~/research`. Billing turns on once App #1 works.

Both run on one Hetzner box (CX22/CAX11, ~€4–7/mo), many-apps-per-box per STACK.md.

## Gate 0 — close the factory gaps (do first)

- [x] `sops` (3.13.3, `~/.local/bin`) + `age` (1.0.0) installed; age keypair at `~/systems/os/.age/keys.txt` (gitignored); `~/systems/.sops.yaml` rule for `secrets.env`. `sx secrets <app>` edits it; `sx provision` installs sops on the box + pushes the key to `~/.config/sops/age-key.txt`; `sx deploy` decrypts `secrets.env` → `.env` on the box (plaintext `.env` no longer ships when `secrets.env` exists).
- [ ] `sx deploy` reloads Caddy when only the Caddyfile changed (`docker compose exec caddy caddy reload` or `--force-recreate caddy`). First trim deploy needed a manual restart.
- [ ] Push `sconix-systems` + `sconix-template-web` to private GitHub (user runs `gh repo create`, then `git push`). CI in `.github/workflows/ci.yml` needs the `_os` clone URL fixed too.

## Phase 1b — batteries (build before App #1 needs them)

### `sconixapp.billing` — ✅ built + **billing loop verified live** (2026-08-31, Stripe test mode)
- checkout → Stripe → webhook (sig verify → parse → upsert) → local `Subscription` row → gate. `/api/usage` shows `plan:"pro", limit:null`; a free client at 5 releases gets 402; the Pro client bypasses it.
- 4 battery bugs found + fixed with regression tests: (1) `from __future__ import annotations` broke `app.openapi()` (function-local Annotated dep → ForwardRef); (2) `dict(stripe_object)` raises in stripe-python 15 → parse the verified payload as plain JSON; (3) `current_period_end` moved onto subscription *items* in 2025+ API versions; (4) `is_live` crashed comparing SQLite-naive vs aware datetime.
- Stripe test setup done: product **Relnotes Pro** `prod_VAjMcxZaYqNWLw`, price **$12/mo** `lookup_key=pro`. Keys in `~/.config/sconix-keys.env` (local) — move to `secrets.env` for deploy.

### `sconixapp.billing` — original build (commit dc4ed40)
- `build_billing_router(get_user_id=, settings=, default_price_id=)` → `POST /api/billing/{checkout,portal,webhook}`.
- `require_plan("pro", get_user_id=)` FastAPI dependency → 402 unless a live sub on that plan.
- Tables `BillingCustomer` (user_id ↔ stripe_customer_id), `Subscription` (status, plan, current_period_end); tz-aware timestamps. App re-exports them for Alembic autogenerate.
- Stripe = source of truth; webhook (`checkout.session.completed`, `customer.subscription.*`) writes local rows; `require_plan` reads local rows. Sync stripe calls run off the loop via `run_in_threadpool`.
- Extra: `sconixapp[billing]` → `stripe`. Settings: `stripe_secret_key`, `stripe_webhook_secret`, `stripe_price_id`.

### `sconixapp.agent` — ✅ built (commit dc4ed40)
- `run_agent(client=, session=, user_id=, area=, model=, system=, messages=, tools=, effort="high")` drives `client.beta.messages.tool_runner`, accounts every turn, writes an `AgentRun` row (turns, in/out/cache tokens, `cost_usd`, `duration_ms`, status), returns `AgentResult(text, run, messages)`. Errors still write the row, then re-raise.
- `pick_model(session, user_id, preferred, ceiling=)` → soft-degrades to `NAV` (Haiku) past the monthly token ceiling. `monthly_tokens()` sums this calendar month.
- Constants `PLANNER`=opus-5, `WORKER`=sonnet-5, `NAV`=haiku-4-5. `cost_usd()` priced per model (cache reads ~0.1× input).
- Extra: `sconixapp[agent]` → `anthropic`. Settings: `anthropic_api_key`, `agent_token_ceiling` (0 = off).
- **TODO in the app:** register tools as `@beta_async_tool`; add `cache_control` on the stable system/prefix.

## App #1 — Relnotes

**Job:** repo + two git refs → structured release notes (Features / Fixes / Breaking / Chore), from the merged PRs in that range.

**MVP — v0 built (commit 2956a48 in `apps/relnotes`), runs locally:**
- [x] `sx new relnotes` (also fixed template: stale `v0.1.4` tag was shadowing the deployable-build fixes → retagged **v0.2.2**; generic Caddyfile; gitignore `next-env.d.ts` + Next agent files; ruff ignores I001/UP in autogen migrations).
- [x] Auth: **real accounts** — `sconixapp.auth` (email+password, httpOnly cookie, signup/login/logout/delete/me). Every route gated on sign-in; releases keyed to `user_id` (FK). Frontend: AuthProvider, SiteHeader w/ user menu, SiteFooter, `/login` `/signup` `/settings` pages. New init migration (users + user_id). Magic-link via Resend still later.
- [x] `POST /api/releases` — `github.py` (compare `base..head` → merged-PR set → digest) → `notes.py` (`run_agent(tools=[])` → JSON → markdown). `GET /api/usage`, `GET/list /api/releases`.
- [x] Billing router wired when `STRIPE_SECRET_KEY` set (`require_plan`-free: gate is a monthly `Release` count vs `free_monthly_limit`, or an active sub).
- [x] Migration (tz-aware) generated + applied on sqlite; 5 tables.
- [x] Web: one page — repo / base / head / tone → notes + copy + `used/limit` line + Upgrade button.
- [x] **Live generation verified** (2026-08-31): `astral-sh/ruff 0.6.0...0.6.1` → 14 PRs → structured notes in ~10s, **$0.0105** on `claude-sonnet-5` (2598 in / 527 out). `usage` counter + `agent_runs` row both written. Needs `ANTHROPIC_API_KEY` in `.env` / `secrets.env`.
- [x] **DEPLOYED + LIVE** (2026-08-31): `sx deploy relnotes` → Hetzner **cx23** (€6.49/mo, hel1) at
      **https://relnotes.204-168-172-115.sslip.io**. Caddy auto-TLS, Postgres+Redis. Prod-verified:
      generation ($0.01/run), rate limit, and the **full Stripe billing loop** — checkout → registered
      webhook (`we_1UAOG4…`, test mode) → `billing_subscriptions` row → Pro gate; free client 402 at 5/mo.
      Box mem 0.9G/3.7G used. Fixed 1 more factory bug → template **v0.2.3** (api Dockerfile now installs
      `sconixapp[extras]` — was dropping stripe/anthropic).
- [x] **Finished product UI** (2026-08-31): real header (usage + Upgrade/Manage-billing), hero,
      generator card, result + copy, **Recent runs** list, 402 upgrade card, post-checkout toast.
      `@app/ui` throughout; `/ui` showcase removed from the product. **Ready to invite users** (on sslip.io).
- [ ] Real domain (Porkbun + Cloudflare) to replace the sslip.io URL.
- [ ] Move to Stripe **live** keys when ready to actually charge (currently test mode).
- [ ] GitHub App / Action + REST token (the sticky distribution) — v2.
- [ ] Model tiering: currently `WORKER` (sonnet-5) at `effort="medium"`, `pick_model` degrades to Haiku past `agent_token_ceiling`. Add `cache_control` on the system prefix. Consider Haiku for small PR sets.

**Cost:** one completion per release, `effort=medium`, `max_tokens=4000`. Expect << $0.05/run on Sonnet.

**Pricing (draft):** free = 5 releases/mo, pro = $12/mo unlimited + API/Action. Revisit after first users.

## App #2 — Skillforge (parked)

**Job:** goal → project-based path (5–7 milestones w/ acceptance criteria) → user submits work (code/text/repo) → agent reviews vs criteria → skill graph tracks demonstrated vs covered.

- Domain-agnostic engine, **seeded with 3–4 project templates** (ML reimpl, backend service, CLI tool, data pipeline) so review quality is guaranteed at launch; widen after.
- `arq` job generates the next milestone in the background.
- Ships free + waitlist; billing on after App #1.
- Skill graph = `skills` + `evidence` tables; render as a list first, graph viz later.

## Design system — `@app/ui` (template-web **v0.3.0**, 2026-08-31)

Direction: **minimal / neutral** — grayscale, near-black accent used sparingly, thin
borders, `system-ui`, 8px radius, flat, content-forward.

- New workspace package `packages/ui` (`@app/ui`). Token layer: Tailwind v4
  `@theme inline` over `:root` / `:root.dark` CSS vars
  (`--bg --surface --fg --muted --muted-fg --border --ring --primary --primary-fg --danger --radius`),
  light + system-dark + `.dark` class.
- Components: `Button` (primary/secondary/outline/ghost/danger/link × sm/md/lg/icon),
  `Input`, `Textarea`, `Label`, `Field`, `Card`+parts, `Badge`, `Skeleton`, `Spinner`, `cn()`.
  Deps: `class-variance-authority`, `clsx`, `tailwind-merge`.
- Wired into `web`: `transpilePackages`, `@import "@app/ui/styles.css"`, `@source "../../../packages/ui/src"`.
- **Retrofitted into Relnotes and deployed** — page + terms + privacy.
- ✅ **v0.4.0** — interactive components: `Dialog`, `DropdownMenu`, `Select`, `Tabs`, `Toaster` (sonner),
  inline icon set, `tw-animate-css`. `/ui` showcase route (living reference, every app gets it).
- ✅ **v0.5.0** — auth **UI kit** (presentational, take `onSubmit`): `AuthCard`, `LoginForm`, `SignupForm`,
  `MagicLinkForm`, `AuthGuard`. All live in Relnotes at `/ui`.
- **Still pending:** `sconixapp.auth` — the **backend** wiring (fastapi-users: user model, JWT + cookie
  backends, register/login/verify/reset routers, magic-link via Resend). Needs the Resend key + a call on
  verification-required vs not. Relnotes keeps anonymous `X-Client-Id`; Skillforge needs real accounts.

## Vendor checklist (wire keys via sops as created)

| vendor | for | when |
|---|---|---|
| Stripe | billing | Phase 1b |
| Porkbun | domain registration | App #1 |
| Cloudflare | DNS + edge (nameservers) | App #1 |
| Resend | magic-link + tx email | App #1 |
| GitHub App | Relnotes repo access (vs PAT) | App #1 v2 |
| Sentry, PostHog | errors, analytics | Phase 2 |

## Open decisions

- Relnotes: final name, domain, price points, free-tier limit.
- Skillforge: name; the 3–4 seed templates; whether reviews need a repo clone or paste-only for MVP.
- Model tiering thresholds (what diff size flips Sonnet→Haiku).
