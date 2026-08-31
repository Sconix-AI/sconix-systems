# Sconix Systems — the stack (decision record)

The apps division. `~/systems/` is to shippable products what `~/research/` is to
experiments: conventions + one small editable engine + a CLI + templates. Same
philosophy — minimal, editable, no platform.

Locked 2026-08-30. Change a row here only with a dated note saying why.

## Shape

```
~/systems/
  os/
    sconixapp/       # Python "batteries" lib, installed --editable into every app's api/
    template-web/    # ONE Copier template -> a deployable web SaaS (its own git repo, tagged)
    template-mobile/ # (later) Expo client wired to a sconixapp backend
    bin/sx           # the CLI, symlinked to ~/bin/sx
    Taskfile.yml     # engine regression tests
    ROADMAP.md
    STACK.md         # this file
  apps/              # generated apps, each its own git repo + deploy target
  inbox.md           # sx cap
  ledger.md          # the money view: app, domain, plan prices, MRR, monthly cost
```

## The bet (expensive to change — committed)

Two languages, never a third: **Python + TypeScript.**

| layer | choice | why |
|---|---|---|
| Backend / API | **FastAPI** (Python), Uvicorn behind Gunicorn | your home language; real OpenAPI, DI, validation; one API serves web + mobile; import ML libs directly |
| ORM + migrations | **SQLModel** + **Alembic** | one type for DB row + API schema |
| DB | **Postgres 16** (container) | portable, no managed bill |
| Cache / queue / rate-limit | **Redis 7** (container) | one dep, three jobs |
| Background + scheduled jobs | **arq** | async-native, Redis-backed, no serverless timeout |
| Auth | **fastapi-users** — JWT access+refresh, OAuth (Google/GitHub/Apple), verify + reset | in-process, owns users in your Postgres, zero extra service |
| Payments | **Stripe** = source of truth · **RevenueCat** bridges iOS/Android IAP | stores force IAP for consumer digital goods |
| Transactional email | **Resend** | cheap, React-email templates |
| Web app | **Next.js 16 (App Router)**, self-hosted (`output: standalone`) in Docker | paved road, SSR marketing + app in one, shadcn out of the box; used as client + BFF, real API is FastAPI |
| Web styling / components | **Tailwind v4** + **shadcn/ui** | 2026 default; components you own, not a dep |
| Mobile app (later) | **Expo SDK 55+** + **Expo Router** | one codebase -> iOS + Android |
| Mobile styling / components | **NativeWind** + **react-native-reusables** | shadcn workflow on native |
| Shared frontend core | **TanStack Query + Zustand + React Hook Form + Zod** — identical on web + mobile | learn once, use on all targets |
| Cross-client sharing | **`packages/api-client`** generated from FastAPI OpenAPI (`openapi-typescript` + `openapi-fetch`); **`packages/shared`** Zod schemas/types | change endpoint once, both clients get new types. NOT sharing UI components (Tamagui/Solito) in v1 — Metro pain |

## The substrate (framework-proof — decide once, never revisit)

| concern | choice |
|---|---|
| Compute | **Hetzner VPS** + Docker Compose + **Caddy** (auto-TLS, per-domain routing); many apps per box until one earns its own |
| Monorepo tooling | **pnpm workspaces + Turborepo** (TS) · **uv** (Python) · top-level `Taskfile.yml` |
| CI/CD | **GitHub Actions** -> build images -> **GHCR** -> `sx deploy` SSHes in -> `docker compose up -d` |
| DNS / edge / WAF | **Cloudflare** free tier |
| Secrets | **SOPS + age** — encrypted files in the repo, decrypt in CI and on the box |
| Errors | **Sentry** free tier — one project each for api / web / mobile |
| Analytics + flags + funnels | **PostHog** — self-host on the VPS or cloud free tier |
| Uptime | **Uptime Kuma** on the box |
| Backups / object storage | **Cloudflare R2** or **Backblaze B2** — nightly `pg_dump` |
| API contract format | **OpenAPI** — clients are generated, never hand-written |
| Auth model | stateless **access token + refresh token** |

## Deliberately deferred

k8s, Terraform, multi-region, teams/orgs/RBAC, a second web template, SSO/SAML
(graduate to Zitadel/Authentik when a B2B deal needs it), Tamagui cross-platform UI,
`template-mobile` (build it when app #1 has users asking for an app).

## Deliberately never (as core)

Vercel lock-in, per-MAU auth pricing (Clerk/Auth0), managed Postgres bills at MVP
stage, a third language.
