# Exact versions used

Every runtime, framework, package and image tag actually used, verified from
the registries (PyPI JSON API, NuGet flat-container API, Maven Central
metadata, Docker Hub / MCR tags) or the tools themselves on 2026-10-09/10.
Update this file whenever a version changes.

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
psycopg[binary] 3.3.6 (cp314 wheels confirmed on PyPI), matplotlib 3.11.2,
pytest-bdd 9.0.0 (PyPI JSON API on 2026-10-15; requires pytest>=7.0.0 and pulls
gherkin-official 42.0.1) for `make bdd`.

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

Pool and threads: 2 Uvicorn workers x DB_POOL_SIZE 10 = 20 connections.

## .NET stack (stacks/dotnet)

| Component | Version | Verified |
| --- | --- | --- |
| SDK image | mcr.microsoft.com/dotnet/sdk:10.0.401 | MCR tags API |
| Runtime image | mcr.microsoft.com/dotnet/aspnet:10.0 (10.0.12) | MCR tags API |
| Npgsql | 10.0.3 | NuGet |
| NetArchTest.Rules | 1.3.2 | NuGet |
| xunit / runner.visualstudio / Test SDK | 2.9.3 / 3.1.5 / 18.10.1 | NuGet |

Pool and threads: NpgsqlDataSourceBuilder.ConnectionStringBuilder.MaxPoolSize
= 20; Kestrel default threading.

## Java stack (stacks/java)

| Component | Version | Verified |
| --- | --- | --- |
| Build image | maven:3.9.16-eclipse-temurin-25 | Docker Hub tags API |
| Runtime image | eclipse-temurin:25-jre | Docker Hub tags API |
| Spring Boot | 4.1.1 (newest stable 4.1.x) | Maven Central |
| postgresql (JDBC) | 42.7.14 | Maven Central |
| ArchUnit / archunit-junit5 | 1.5.1 | Maven Central |
| Jackson (transitive via Boot 4, Jackson 3: tools.jackson) | Boot-managed | - |
| jackson-databind (2.x, only in booking-adapter-out-postgres) | Boot-managed | - |

Pool and threads: HikariCP maximum-pool-size 20; Tomcat default
platform-thread pool (spec: virtual threads belong to post 2).

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
  duplicates=0) were invalid evidence and were removed at the author's
  instruction. The python rows from that night also carry p99_ms=0 (the
  p(99) trend-stat fix landed after them); dotnet and java rows are complete.
- Npgsql 10: `NpgsqlDataSourceBuilder` rejects URI-style connection strings
  (`postgresql://...`) and has no `MaxPoolSize` builder method and no
  pool keywords in the connection string; the bootstrap translates
  DATABASE_URL into keywords and sets `ConnectionStringBuilder.MaxPoolSize`.
- Spring Boot 4 is Jackson 3 (`tools.jackson.*`): `JsonMapperBuilderCustomizer`
  replaces `Jackson2ObjectMapperBuilderCustomizer`; quoted numbers are rejected
  through `withCoercionConfigDefaults`.
- booking-adapter-out-postgres/pom.xml also declares jackson-databind
  (Boot-managed 2.x) for reading/writing the stored-result jsonb; the CLAUDE.md
  tree comment for that pom lists three dependencies.
- VS Code: the root .venv also carries an editable install of stacks/python
  (machine-local, gitignored) so Pylance resolves `booking` and fastapi; stack
  builds and tests still run only in containers.

## Observability overlay (infra/observability, opt-in, off for measured runs)

| Component | Version | Verified |
| --- | --- | --- |
| opentelemetry-collector-contrib (otel-agent DaemonSet, otel-cluster Deployment) | 0.163.1 (arm64 confirmed in the image index; 0.163.0 is absent from ghcr) | `docker manifest inspect ghcr.io/open-telemetry/opentelemetry-collector-releases/opentelemetry-collector-contrib:0.163.1`, 2026-10-17 |
| grafana/otel-lgtm (backend + Grafana) | 0.37.0 (amd64 and arm64) | Docker Hub tags API, 2026-10-17 |
