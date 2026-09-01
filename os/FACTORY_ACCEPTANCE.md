# Sconix Factory Acceptance

This is the gate for calling the Sconix factory usable on a clean Linux or WSL
environment. It does not contact a server, create a GitHub repository, or mutate
an application outside its temporary directory.

## Install

From a clone of `sconix-systems`, run:

```bash
bash os/install.sh
```

The host must provide `git` and `uv`. The installer provisions `copier`, installs
the local `sconixcore` package, and links `sx` into `~/bin`.

## Acceptance test

Run the factory check from any clone:

```bash
SKIP_WEB=1 bash os/test_template.sh
```

The check generates a temporary application, verifies its rendered files and
strict manifest, installs its API dependencies, and runs API lint and tests. Set
`SKIP_WEB=0` to include the frontend install and production build.

## Definition of done

- `sconixcore` installs from the local repository.
- `sx new` has a valid application manifest and agent context.
- `sconix-inspect --strict` accepts the generated project.
- The generated API passes lint and tests.
- The generated frontend builds when Node and pnpm are available.
- Deployment actions remain plan/approval gated; this check never contacts a host.

This gate proves factory reproducibility, not production readiness. A separate
disposable-server exercise must verify deployment, canary, promotion, rollback,
and teardown.
