# Sconix Systems — ledger

The money view. One block per app (`sx ledger "..."` appends a dated note).

| app | domain | status | plans | MRR | monthly cost |
|-----|--------|--------|-------|-----|--------------|
| _(none yet)_ | | | | $0 | $0 |

## Notes

- 2026-08-30 — division created. Stack locked in `os/STACK.md`. Target infra cost:
  ~€4/mo (one Hetzner CX22) + domains, so first paid customer is already profit.
- **2026-08-30** — Systems OS skeleton built: sconixapp batteries (config/db/security/logging/health, 7 tests), sx CLI, template-web v0.1.0 (FastAPI+Next16+packages). Engine 'task test' green. Stack locked in os/STACK.md.
- **2026-08-30 23:33** — deploy trim -> trim.204-168-172-115.sslip.io (04a901d)
- **2026-08-30 23:34** — deploy trim -> trim.204-168-172-115.sslip.io (9e5b5fa)
- **2026-08-30 23:39** — deploy trim -> trim.204-168-172-115.sslip.io (2cadef9)
- **2026-08-31** — **first real deploy validated.** `sx provision` + `sx deploy trim` to a Hetzner cx23 (€6.49/mo, hel1): live HTTPS via Caddy auto-TLS on `trim.<ip>.sslip.io`, full create→redirect→click-count→stats path green. Surfaced + fixed 5 factory bugs (build context, sconixapp path-pin, web/public, Caddy /api strip, tz-aware timestamp) → template-web v0.1.1. Box + key + IP destroyed after; spend ≈ €0.05.
- **2026-08-31 00:58** — deploy relnotes -> relnotes.204-168-172-115.sslip.io (7438d74)
- **2026-08-31 01:00** — deploy relnotes -> relnotes.204-168-172-115.sslip.io (416e633)
- **2026-08-31** — **Relnotes LIVE.** `sx deploy relnotes` to a Hetzner **cx23** (€6.49/mo, hel1) at https://relnotes.204-168-172-115.sslip.io — Caddy auto-TLS, Postgres+Redis. Verified in prod: generation (ruff 0.6.0→0.6.1, 14 PRs, $0.01), per-IP rate limit, and the **full Stripe billing loop** (checkout → registered webhook `we_1UAOG4…` → `billing_subscriptions` row → Pro gate; free client 402 at 5/mo). Fixed 1 more factory bug: api Dockerfile dropped `sconixapp[extras]` → no stripe on the box → template **v0.2.3**. Box still running (first paying-capable app). Stripe = TEST mode.
- **2026-08-31 01:17** — deploy relnotes -> relnotes.204-168-172-115.sslip.io (f982d2e)
- **2026-08-31 01:24** — deploy relnotes -> relnotes.204-168-172-115.sslip.io (3a0a848)
- **2026-08-31 01:28** — deploy relnotes -> relnotes.204-168-172-115.sslip.io (77b543d)
- **2026-08-31 01:34** — deploy relnotes -> relnotes.204-168-172-115.sslip.io (4eb7c3b)
- **2026-08-31 01:38** — deploy relnotes -> relnotes.204-168-172-115.sslip.io (1950a41)
- **2026-08-31 01:51** — deploy relnotes -> relnotes.204-168-172-115.sslip.io (a18020b)
- **2026-08-31** — Relnotes became a **real app**: `sconixapp.auth` (email+password, cookie) + gated routes + user-owned releases; frontend gained AuthProvider, header w/ user menu, footer, `/login` `/signup` `/settings`. `@app/ui` up to v0.5.2 (Radix Dialog/DropdownMenu/Select/Tabs/Toaster, auth UI kit, Button asChild). Box DB reset + redeployed. Stripe still TEST.
- **2026-08-31 01:55** — deploy relnotes -> relnotes.204-168-172-115.sslip.io (865f28b)
- **2026-08-31 02:26** — deploy relnotes -> relnotes.204-168-172-115.sslip.io (05c9af8)
- **2026-08-31 02:29** — deploy skillforge -> skillforge.204-168-172-115.sslip.io (8dbf98f)
- **2026-08-31** — **Skillforge live** + **two apps on one box**. Built Skillforge (agentic project-based learning: plan path -> milestones -> submit -> agent review -> skill graph) on template v0.7.0. Shipped the **shared edge**: one box-level Caddy (`sx edge`) terminates TLS for every app; apps join `sconix_edge`, drop `/srv/edge/sites/<app>.caddy`, no per-app Caddy/ports. Migrated Relnotes onto it (brief downtime). Both live: relnotes + skillforge.<ip>.sslip.io on one cx23 (€6.49/mo), 1.4G/3.7G used. Fixes: agent adaptive-thinking only on supporting models; Next standalone HOSTNAME=0.0.0.0; pg/redis ports -> dev override. Skillforge Stripe OFF (free).
