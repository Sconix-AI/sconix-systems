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
