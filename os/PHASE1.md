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

### `sconixapp.billing` — ✅ built (commit dc4ed40)
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

**MVP**
- `sx new relnotes`
- Auth: magic link (fastapi-users). Billing: one `pro` plan gates >N generations/mo.
- One agent loop: GitHub tool (list merged PRs between refs, fetch titles/bodies/labels) → Tool Runner → markdown + JSON out.
- UI: paste repo URL + pick two tags → rendered notes + copy button + "regenerate with tone X".
- Deliver: web form now; GitHub Action + REST endpoint next (that's the sticky distribution).
- Deploy to the box, real domain (Porkbun + Cloudflare).

**Cost:** runs on release, not per keystroke. Sonnet default, Haiku for small diffs. Cache repo/style prefix. Expect << $0.10/run.

**Pricing (draft):** free = 5 repos-notes/mo, pro = $12/mo unlimited + API/Action. Revisit after first users.

## App #2 — Skillforge (parked)

**Job:** goal → project-based path (5–7 milestones w/ acceptance criteria) → user submits work (code/text/repo) → agent reviews vs criteria → skill graph tracks demonstrated vs covered.

- Domain-agnostic engine, **seeded with 3–4 project templates** (ML reimpl, backend service, CLI tool, data pipeline) so review quality is guaranteed at launch; widen after.
- `arq` job generates the next milestone in the background.
- Ships free + waitlist; billing on after App #1.
- Skill graph = `skills` + `evidence` tables; render as a list first, graph viz later.

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
