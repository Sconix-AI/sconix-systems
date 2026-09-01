# Project Manifest v1 Migration

New projects will use `sconix.yaml`. Existing `app.yaml` and `project.yaml` remain readable until
an explicit migration is accepted.

## Field mapping

| Existing | v1 |
|---|---|
| `name`, `slug`, `created`, `tags` | unchanged |
| `pitch` | `summary` |
| `question` | retained; required for `kind: research` |
| `status` | `lifecycle.status` |
| `domain` | `endpoints.production` when a real URL exists |

Systems statuses map `scaffold → draft`, `building → active`, `live → live`, and
`parked → parked`. Research statuses map `active → active`, `paused → paused`, `done → completed`,
and `abandoned → abandoned`.

## Example application

```yaml
schema: sconix.dev/project/v1
kind: application
name: Relnotes
slug: relnotes
summary: release notes from merged PRs between two git refs
created: 2026-08-31
profile: {name: ai-saas, version: "1"}
lifecycle: {status: live}
endpoints: {production: "https://relnotes.204-168-172-115.sslip.io"}
capabilities:
  auth: {provider: sconix-cookie}
  agent: {provider: anthropic}
  billing: {provider: stripe}
  deploy: {provider: compose-ssh}
commands:
  test: {run: task test, risk: local-write, approval: never}
  deploy:
    run: sx deploy relnotes
    risk: external-write
    approval: always
    verify: [healthz]
agents:
  instructions: [AGENTS.md]
  context: [README.md, app.yaml]
```

## Compatibility loader

The future loader should prefer `sconix.yaml`; otherwise detect a legacy manifest; convert it to
the v1 in-memory model; report inferred and missing fields without mutation; emit JSON through
`sconix inspect --json`; and write only through an explicit migration command.

## Deferred until Pilot requirements arrive

- Principal, action, approval, execution, incident, and audit schemas.
- Provider secret/configuration contracts.
- Organization ownership and policy attachment.
- Whether command `run` becomes an argv array before v1 is stable.
