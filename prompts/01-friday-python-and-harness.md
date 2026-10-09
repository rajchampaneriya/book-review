# P1. FastAPI stack and the harness

**When:** Fri 9 Oct, 18:00 to 23:00 IST.
**Session:** a new Claude Code session at the repo root, in plan mode.
**Before you start:** the starter files (`.gitignore`, `.gitattributes`, `CLAUDE.md`, `.claude/`,
`docs/`, `prompts/`, `tools/`, `LICENSE`) are committed, `python3 tools/arch/selftest.py` reports
114/114, and P0 is done.

## Prompt (paste as is)

```text
Read CLAUDE.md and docs/exp3-spec.md first. Pay particular attention to the hexagonal architecture section, the folder structure and rule G0. The CLAUDE.md tree is the whole repository: create every file it lists and nothing else. If you need a file it does not list, stop and ask me.

Task: build the experiment 3 harness and the FastAPI stack end to end, so that these work on this machine:
  make doctor
  make up
  make unit STACK=python
  make arch STACK=python
  make contract STACK=python
  make exp3 STACK=python VARIANT=naive FAULT=0.05 RUN=1
  make exp3 STACK=python VARIANT=v2 FAULT=0.05 RUN=1

Work in this order:
1. stacks/python skeleton: every file in the Python tree in CLAUDE.md, with exactly those names (stubs are fine for now), and nothing else. Copy tools/arch/templates/python/importlinter.toml to stacks/python/importlinter.toml verbatim (do not edit it). The Dockerfile has the stages build, unit, arch and runtime from the spec. Create the Makefile with ENGINE detection and the unit and arch targets: make arch runs python3 tools/arch/check_hexagonal.py python (it fails if a listed file is missing or an unlisted file exists), then builds the arch stage, which runs lint-imports --config ../importlinter.toml from src/. Prove both checks work: add one deliberate violation (application/services importing the postgres adapter), run make arch and show it failing, revert, show it passing.
2. Domain, ports and services with unit tests in tests/unit that use InMemoryBookingStore from tests/unit/fakes.py: both services, the request hash, KeyAlreadyClaimedError, and the Created / Replayed / Conflict / InFlight outcomes.
3. Outbound Postgres adapter (PostgresBookingStore and its transaction, plain SQL, SQLSTATE 23505 mapped to KeyAlreadyClaimedError) and inbound HTTP adapter (routes_naive.py, routes_v2.py, health.py, schemas.py with Pydantic extra="forbid", fault_hook.py, error_handlers.py). Routes depend on the driving-port Protocols, never on services. Bootstrap (settings.py, container.py, main.py) wires services to ports.
4. infra/ and db/, exactly the files in the CLAUDE.md tree: the k3d cluster (host 8081-8083 to NodePorts 30081-30083, host 55432 to NodePort 30432), Postgres (current major; verify the image tag) on NodePort 30432, db/schema.sql applied per stack schema by apply-schema.sh, one Deployment and NodePort Service per stack with container port 8080, requirements-host.txt, and the make targets doctor (also creates .venv), up, down and deploy.
5. contracts/tests: all eight contract tests in the files the tree lists, runnable against any stack with make contract STACK=<stack>, reading the database at localhost:55432.
6. harness/__init__.py, harness/db.py, harness/exp3_run.py and harness/k6/exp3.js. make exp3 truncates the stack's tables, runs k6, counts in the database and appends one row to results/exp3/runs.csv.
7. versions.md with the exact versions you installed, verified from the registries.

Out of scope tonight: .NET, Java, the matrix runner, the summary, the chart, MCP.

Before writing any code, give me a plan with:
- the files you will create, matched line by line against the CLAUDE.md tree (stacks/python, db, infra, contracts, harness, the Makefile and requirements-host.txt); there should be no deviation
- the method signatures of the driving and driven ports, and the outcome types
- the Python Postgres driver you chose and why (it must support Python 3.14)
- what each Dockerfile stage (build, unit, arch, runtime) copies and runs
- anything in the spec you think is wrong, ambiguous or risky
Then wait for my approval.

When the build is done, run the seven commands above and python3 tools/arch/check_hexagonal.py --all, and show me their output and the two runs.csv rows. If a step fails twice, stop and tell me what you tried. Commit in small steps with conventional messages. Do not push.
```

## Your review checklist before approving the result

Architecture:

- [ ] `python3 tools/arch/check_hexagonal.py python` and `make arch STACK=python` both pass; lint-imports reports 5 kept, 0 broken.
- [ ] `stacks/python/importlinter.toml` is an unmodified copy of the template.
- [ ] The commit history shows the deliberate violation failing `make arch`, then reverted.
- [ ] `check_hexagonal.py python` reports nothing "not in" or "missing from the folder structure": no extra
      `utils.py`, `conftest.py` or lock file, and no listed file left as an empty stub.
- [ ] `domain/` and `application/` import nothing outside the standard library.
- [ ] `PostgresBookingStore` raises `KeyAlreadyClaimedError`; no driver exception reaches a service.
- [ ] Services return outcomes (Replayed, Conflict); HTTP status codes appear only in the HTTP adapter.
- [ ] Routes import ports, not services; the fault hook lives in the HTTP adapter.

Behaviour:

- [ ] The naive files have the "INTENTIONALLY NAIVE BASELINE" header and no key, constraint or retry.
- [ ] In v2, the key is claimed first, in the same transaction as the booking and the charge.
- [ ] The fault hook does nothing unless `FAULT_INJECTION=enabled`.
- [ ] k6 sends `X-Fault` on the first attempt only, and retries with the same key.
- [ ] Duplicates are counted with SQL, not from k6 output.
- [ ] Contract test 6 (20 concurrent duplicates give one booking) passes.
- [ ] The naive run at 5% shows duplicates; the v2 run shows none. If not, ask why before moving on.
