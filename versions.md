# Exact versions used

Every runtime, framework, package and image tag actually used, verified from
the registries (PyPI JSON API, Docker Hub) or the tools themselves on
2026-10-09/10. Update this file whenever a version changes.

## Host (macOS 27.0, arm64)

| Tool | Version | Verified |
| --- | --- | --- |
| Docker Desktop | 29.6.2 (build dfc4efb) | `docker version` |
| k3d | v5.9.0 (brew) | `k3d version` |
| kubectl | v1.36.1 (client) | `kubectl version --client` |
| k6 | v2.3.0 (go1.27.1, darwin/arm64, brew) | `k6 version` |
| jq | 1.8.2 (brew) | `jq --version` |
| Python (host) | 3.14.2 (Homebrew) | `python3 --version` |
| git | 2.48.1 | `git --version` |

Host `.venv` (requirements-host.txt): pytest 9.1.1, httpx 0.28.1,
psycopg[binary] 3.3.6 (cp314 wheels confirmed on PyPI), matplotlib 3.11.2.

## Python stack (stacks/python)

| Component | Version | Verified |
| --- | --- | --- |
| Base image | python:3.14-slim (pushed 2026-10-09) | Docker Hub tags API |
| fastapi | 0.143.0 | PyPI |
| uvicorn | 0.54.0 | PyPI |
| pydantic (transitive via fastapi, pinned for record) | 2.14.0 | PyPI |
| asyncpg | 0.32.0 (cp314 wheels for macOS arm64 and manylinux) | PyPI |
| pytest | 9.1.1 | PyPI |
| import-linter | 2.15 | PyPI |

## Java stack (stacks/java, P2) — not built yet

## .NET stack (stacks/dotnet, P2) — not built yet

## Infrastructure

| Component | Version | Verified |
| --- | --- | --- |
| k3s (inside k3d) | k3d v5.9.0 default (k3s v1.36.x) | `kubectl` server printout |
| postgres | 18.6 (Debian, pushed 2026-10-07; newest major) | Docker Hub tags API |
| Postgres client in contract tests/harness | psycopg 3.3.6 | PyPI |

## Deviations and notes

- Postgres 18+ requires the volume mounted at `/var/lib/postgresql` (not
  `.../data`); the manifest mounts the parent directory.
- The measured-run fault toggle is `kubectl set env` on the stack Deployment
  (on before k6, restored after), because the deployments must default to
  `FAULT_INJECTION` unset for contract test 8.
- runs.csv rows written before the fault-injection toggle and the p(99) fix
  (the RUN=0 smoke row and the first python/naive/f0.05/r1 row with
  duplicates=0) are invalid evidence; the author should delete them from
  results/exp3/runs.csv before the matrix (results/ is protected for the agent).
