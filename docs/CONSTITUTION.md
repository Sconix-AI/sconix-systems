# Sconix Platform Constitution

Status: draft for the first agent-native platform checkpoint.

## Purpose

Sconix is an open, agent-native software operating system for turning ideas into researched,
deployed, and continuously improved systems. It gives humans and agents a shared project
contract, consistent lifecycle operations, explicit safety boundaries, and evidence about what
happened. It optimizes for the shortest trustworthy path from intent to verified outcome, not
the largest framework surface.

## Users

Sconix serves individual developers, teams and companies, coding and operational agents,
researchers, and CI or service principals.

## Principles

1. **Agent-native, human-legible.** Every important operation is discoverable and structured
   for agents while remaining understandable and executable by humans.
2. **Opinionated defaults, replaceable boundaries.** The paved path works without a design
   session. Replaceability is added at proven boundaries, not imagined universal interfaces.
3. **Evidence before abstraction.** Shared capabilities come from repeated real use or an
   unavoidable safety requirement.
4. **Stable contracts, evolvable implementations.** Manifests, actions, and capability
   interfaces are versioned; breaking changes require migrations.
5. **Explicit authority.** Every consequential action has a principal, scope, permissions,
   risk class, and approval policy. Tool access does not imply authority.
6. **Verification completes an action.** Command success is not outcome success. Mutations
   remain incomplete until postconditions pass or recovery is invoked.
7. **Inspectable memory.** Decisions, incidents, experiments, and outcomes use explicit
   records as sources of truth. Semantic retrieval is only an index.
8. **Local-first, production-capable.** Defaults run with minimal local infrastructure and
   graduate to production without changing the conceptual model.
9. **Incremental adoption.** Users may adopt the CLI, profiles, libraries, adapters, or policy
   independently.
10. **First-class escape hatches.** Users own generated code, can operate without a model,
    replace providers, export state, and avoid platform lock-in.

## Boundaries

Sconix owns project manifests and lifecycle vocabulary; versioned profiles; capability and
provider declarations; typed actions, principals, policies, approvals, and audit records;
context and memory conventions; and validation, upgrade, deployment, and recovery orchestration.

Sconix does not own application domain logic, model intelligence, a universal cloud/database/UI
framework, hidden autonomous authority, or replacements for Git, containers, and package
managers where composition is sufficient.

## Product shape

- Core defines project, action, principal, policy, context, and extension contracts.
- Profiles provide coherent starts such as `web-saas`, `ai-app`, `agent-service`, and `research`.
- Capabilities express needs; providers implement them.
- Systems handles persistent products and operations.
- Research handles experiments, evidence, artifacts, and reports.

Systems and Research share contracts only where their semantics genuinely match.

## Compatibility and extensions

Public schemas are versioned; releases are immutable; users choose when to upgrade; supported
upgrades include validation and migration; deprecations precede removal. Extensions may add
profiles, capabilities, providers, validators, context sources, or actions, but must declare
compatibility, permissions, side effects, and configuration and cannot bypass policy or auditing.

## Success test

A human or agent entering a project must reliably answer: what is this project, what can I do,
what authority do I have, what will change, what happened before, and how do I verify or recover?
Generating code alone is not success.
