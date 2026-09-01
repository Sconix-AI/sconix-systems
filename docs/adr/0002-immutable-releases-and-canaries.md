# ADR 0002: Immutable releases before traffic canaries

- Status: accepted
- Date: 2026-08-31

## Decision

Every deployment requires a content-addressed plan, a separate attributable one-time approval,
and an exact Git SHA/host/domain match. Approval is consumed before remote mutation. Source is
staged under `/srv/releases/<app>/<sha>-<plan-id>` and promoted into the runtime directory.
Rollback restores one immutable source release, rebuilds containers, and verifies health and
readiness. It never guesses how to reverse database migrations.

## Canary constraint

The current app Compose files attach production aliases such as `relnotes-api` to the shared edge
network. Starting a parallel Compose project would reuse those aliases and could receive live
traffic unpredictably. Therefore `sx canary` is blocked until the template provides release-scoped
network aliases and generated edge routes.

The required next template contract is:

- release/slot-specific API and web aliases;
- an isolated canary database and Redis;
- a canary-only hostname or weighted edge route;
- automatic teardown;
- promotion by switching an edge route, not rebuilding production;
- verification and rollback records using the same plan ID.

The lifecycle uses separate one-time approvals for each mutating phase:

1. `sx canary` stages and verifies an isolated release.
2. `sx promote` creates a new approved plan bound to the verified canary plan, then switches
   the production edge route while keeping the previous route available for rollback.
3. `sx teardown` requires another approval and removes the canary only when it is not serving
   production traffic.

The canary stack has its own database and Redis volumes. Applications that need production data
must provide an explicit data-cloning or compatibility strategy before treating a canary as a
promotion candidate; Sconix does not copy or reverse database state implicitly.

Shipping a command that merely starts a second stack on the current network is rejected as unsafe.
