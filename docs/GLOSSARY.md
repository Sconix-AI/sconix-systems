# Sconix Glossary

These terms are contract language for schemas, APIs, and architecture records.

- **Project:** Discoverable work with a Sconix manifest, lifecycle, capabilities, operations,
  and source-controlled state.
- **Kind:** Broad project semantics. Version 1 defines `application` and `research`.
- **Profile:** Versioned coherent defaults for a class of projects; not a permanent cage.
- **Capability:** A project need such as auth, agent execution, billing, or deployment.
- **Provider:** A concrete implementation of a capability.
- **Adapter:** Code translating a provider into a Sconix capability contract.
- **Extension:** A versioned package adding profiles, providers, validators, context, or actions.
- **Principal:** The accountable human, agent, CI job, or service performing an action.
- **Service principal:** A non-human principal with explicit credentials, permissions, and lifecycle.
- **Action:** Typed request to observe or change state, declaring scope, risk, approval, and verification.
- **Action plan:** Immutable proposed actions and effects; it is not authority to execute.
- **Permission:** A grant to perform an action within a scope.
- **Policy:** A deterministic rule that permits, denies, constrains, or requires approval.
- **Approval:** Attributable, scoped, expiring authorization for a specific action or plan.
- **Risk:** `read-only`, `local-write`, `external-write`, or `destructive` consequence class.
- **Execution:** One attempt to carry out an approved action.
- **Verification:** Evaluation of declared postconditions after execution.
- **Audit event:** Append-only evidence of proposal, approval, execution, verification, or recovery.
- **Context source:** Authoritative input such as manifests, decisions, Git, tests, or incidents.
- **Context pack:** Bounded task-specific context with provenance and applicable permissions.
- **Memory record:** Structured durable knowledge about a decision, experiment, incident, or outcome.
- **Memory index:** Disposable retrieval layer over authoritative memory records.
- **Evidence:** Tests, metrics, logs, probes, artifacts, or observations supporting an outcome.
- **Manifest:** Versioned declaration of project identity, lifecycle, capabilities, and commands.
- **Validator:** Deterministic check of project structure, configuration, contracts, or behavior.
- **Artifact:** Durable output such as a build, model, report, release, or action record.
- **Release:** Immutable application build eligible for deployment and rollback.
- **Run:** Reproducible computational execution with configuration, environment, metrics, and artifacts.
