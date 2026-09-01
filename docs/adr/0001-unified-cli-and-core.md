# ADR 0001: One CLI over specialized engines

- Status: proposed
- Date: 2026-08-31

## Context

Sconix currently exposes `sconix` for Research and `sx` for Systems. Both commands embed
discovery and orchestration in Bash. External users and agents need one discoverable interface,
structured output, versioned contracts, and reusable logic outside a shell process.

## Decision

Adopt `sconix` as the public CLI. Keep Systems and Research as specialized engines behind a small
Python `sconixcore` layer. Core owns manifest discovery, validation, inspection, command metadata,
and later action/principal contracts. Engines own domain behavior.

The CLI is an adapter over importable application services. Human output is the default; every
inspection and operation must support a stable structured result. Bash remains acceptable for
provider implementation scripts but is not the public contract or source of lifecycle semantics.

## Migration

1. Introduce read-only `sconix inspect` behavior through `sconixcore`.
2. Make the future CLI dispatch from `sconix.yaml` kind and capabilities.
3. Wrap existing `sconix` and `sx` operations without changing behavior.
4. Add structured plans/results before moving mutating operations.
5. Deprecate direct `sx` usage only after command parity and migration documentation.

## Consequences

Project understanding becomes reusable by CLI, SDK, MCP, and agents. Specialized engines remain
independent. During migration there are two command surfaces, and wrappers must not hide existing
safety behavior or silently rewrite manifests.
