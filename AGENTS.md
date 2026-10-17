# wcf-physics-agentic: instructions for Codex

Runnable prototypes that re-test service-design rules from *Programming WCF Services*, 4th Edition
(Juval Lowy and Michael Montgomery), in .NET 10, Spring Boot on Java 25 and Python FastAPI. The MVP
(due Sunday 11 Oct 2026, 23:00 IST) measures one rule: when the response to a committed booking is
lost and the client retries, the service must not create a second booking or a second charge.
The spec below is the source of truth for behaviour; if you think it is wrong, say so and wait.

@docs/exp3-spec.md

## Who does what

- You (Codex) write code, scripts, Kubernetes manifests, tests, READMEs and code comments.
- You do not write article or blog prose, and you make no claims about the book. The author does.
- Work on a branch and open a pull request for every change; never push to `main` directly. The
  author reviews every change, and a pull request merges into `main` only when the author asks.
  Never add a git remote, and never publish.

## Architecture: hexagonal (ports and adapters), identical in every stack

| Layer | Holds | May depend on |
| --- | --- | --- |
| domain | Booking, Charge, DepositAmount, the invalid-deposit error | Standard library only |
| application ports in | Driving ports: the two use-case interfaces, BookSessionCommand, BookingConfirmation, outcomes (Created, Replayed, Conflict, InFlight) | domain |
| application ports out | Driven ports: BookingStore (find_key, run a transaction), BookingTransaction (claim_key, add_booking, add_charge, store_result), StoredKey, the key-already-claimed error | domain |
| application services | BookSessionNaiveService, BookSessionIdempotentService, the request hash | ports, domain |
| inbound adapter `<name>` | HTTP now, MCP later: DTOs, validation, status codes, the fault hook | application ports, domain |
| outbound adapter `<name>` | Postgres: the BookingStore implementation, SQL, error mapping | application ports, domain |
| bootstrap | Composition root: settings, wiring services to ports, start-up | everything |

Adapters never depend on each other or on services (they call ports). Ports never depend on
services. Frameworks and drivers live only in adapters and bootstrap. Transactions live inside the
Postgres BookingStore, never as `@Transactional` or similar in the application.

## Folder structure (complete; enforced by tools/arch/check_hexagonal.py)

This tree is the whole repository; the checker reads it from the block below. Two spaces per level;
names ending in `/` are folders, and one folder line may hold several segments
(`src/main/java/work/rajc/booking/domain/`); text after `#` is a comment. Create every file listed
(stubs are fine while building) and nothing else. `*` matches within one name and `**` any path below
its folder; entries marked `(optional)` may be absent, and so may everything under them. Ignored everywhere: `.git/`, `.venv/`, `venv/`,
`__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `.import_linter_cache/`,
`*.egg-info/`, `node_modules/`, `target/`, `bin/`, `obj/`, `TestResults/`, `.idea/`,
`.DS_Store`. Review notes, the task backlog and BDD specifications are not stack code: put them under
the optional `TASKS.md`, `docs/review/` and `bdd/` entries without asking. For any other file that is
not listed, stop and ask the author to add it here first. `AGENTS.md`, when present, carries this tree
verbatim; the checker compares the two.
Every service listens on port 8080 inside its container. Stack builds and tests run in containers,
so the host needs no JDK, .NET SDK or Python 3.14.

<!-- structure:begin -->
```text
.gitignore                                # starter kit; build outputs, caches, .venv/, .claude/settings.local.json, CLAUDE.local.md
.gitattributes                            # starter kit; LF line endings everywhere
CLAUDE.md                                 # these instructions (protected)
CLAUDE.local.md                           # (optional) author's private notes, gitignored
AGENTS.md                                 # (optional) Codex instructions (same role as CLAUDE.md)
.codex/                                   # (optional) Codex agent configuration (mirrors .claude/)
  **                                      # config.toml, hooks.json, hooks/
LICENSE                                   # MIT
Makefile                                  # the commands below; ENGINE = docker or podman, detected
README.md                                 # code README, written in P5
TASKS.md                                  # (optional) review backlog: Done, In Progress, Not Started, Open Questions, execution sequence
requirements-host.txt                     # pinned host tools for .venv: pytest, pytest-bdd, httpx, psycopg[binary], matplotlib
versions.md                               # every runtime, framework, package and image tag actually used
.vscode/                                  # editor config: interpreter, pytest discovery, extension recommendations
  settings.json                           # default interpreter ${workspaceFolder}/.venv, pytest discovery on bdd/steps
  extensions.json                         # recommends the Cucumber Open (Gherkin) extension
.claude/                                  # protected
  settings.json                           # hooks, auto memory off
  settings.local.json                     # (optional) written by Claude Code when you approve permissions
  hooks/
    protect-files.sh                      # blocks edits to protected paths
    arch-gate.sh                          # Stop hook: runs check_hexagonal.py --all
  rules/
    naive-baseline.md                     # loads when naive files are touched
.github/                                  # (optional) P5
  workflows/
    contract.yml                          # runs make contract per stack
docs/
  exp3-spec.md                            # experiment 3 spec (source of truth)
  review/                                 # (optional) principal review: BDD_REVIEW.md, architecture .excalidraw and its PNG preview
    **
prompts/
  README.md
  00-observation.md
  01-friday-python-and-harness.md
  02-saturday-dotnet-java.md
  03-matrix-summary-chart.md
  04-independent-review.md
  05-readme-and-publish.md
  06-stretch-mcp-tool.md
observations/                             # protected; the author copies P0 output here
  **                                      # exp3/<stack>/META.md and exp3/<stack>/output/...
tools/                                    # protected
  arch/
    check_hexagonal.py                    # static architecture, naming and structure checker
    selftest.py                           # proves the checker catches every violation
    templates/
      python/
        importlinter.toml                 # Python architecture tests
      java/
        HexagonalArchitectureTest.java    # Java architecture tests (ArchUnit)
      dotnet/
        HexagonalArchitectureTests.cs     # .NET architecture tests (NetArchTest)
db/
  schema.sql                              # tables with a {stack} schema placeholder
infra/
  k3d/
    cluster.yaml                          # cluster wcf-physics; host 8081-8083 -> NodePorts 30081-30083; host 55432 -> 30432
  k8s/
    namespace.yaml                        # namespace wcf-physics
    postgres.yaml                         # Secret (local dev defaults), Deployment, NodePort Service 30432
    dotnet.yaml                           # Deployment (image wcf-physics/dotnet:dev) and NodePort Service 30081
    java.yaml                             # Deployment (image wcf-physics/java:dev) and NodePort Service 30082
    python.yaml                           # Deployment (image wcf-physics/python:dev) and NodePort Service 30083
    rbac.yaml                             # ServiceAccounts, Roles, ClusterRoles and bindings
    network-policy.yaml                   # default deny plus one allow rule per permitted connection
    schema-job.yaml                       # Job: applies the rendered schema per stack
    duplicate-audit.yaml                  # CronJob: read-only duplicate count per schema
  mesh/                                   # (optional) Istio ambient overlay, off for measured runs
    gateway.yaml                          # Gateway and HTTPRoutes for host traffic
    security.yaml                         # PeerAuthentication and AuthorizationPolicies
    traffic.yaml                          # timeouts, retries (v2 only), weighted routes
  observability/                          # (optional) OpenTelemetry overlay, off for measured runs
    otel-agent.yaml                       # DaemonSet collector
    otel-cluster.yaml                     # Deployment collector (k8s_cluster)
    lgtm.yaml                             # grafana/otel-lgtm backend and Grafana
    dashboards/
      wcf-physics-overview.json           # provisioned dashboard
  scripts/
    doctor.sh                             # make doctor
    up.sh                                 # make up: cluster, Postgres, schemas, all stacks
    down.sh                               # make down
    deploy.sh                             # make deploy: build target runtime, k3d image import, rollout
    apply-schema.sh                       # renders db/schema.sql per stack schema and applies it
    scale.sh                              # scales one stack to 0 or 1 replicas (used by the matrix)
    mesh-up.sh                            # make mesh-up: installs the Istio ambient overlay
    observe-up.sh                         # make observe-up: installs the OpenTelemetry overlay
contracts/
  pytest.ini
  tests/
    conftest.py                           # STACK -> base URL; Postgres at localhost:55432, schema = STACK
    test_health.py                        # contract test 1
    test_naive_bookings.py                # contract test 2
    test_v2_bookings.py                   # contract tests 3 to 6
    test_validation.py                    # contract test 7
    test_fault_hook.py                    # contract test 8
    test_mcp_tool.py                      # (optional) P6: the book_session tool through the MCP client
bdd/                                      # (optional) Gherkin specification and thin pytest-bdd steps; runs from the host .venv
  **                                      # features/*.feature, steps/*.py
harness/
  __init__.py
  db.py                                   # Postgres at localhost:55432: truncate, counts
  hostinfo.py                             # writes results/exp3/host.json
  exp3_run.py                             # make exp3 (python -m harness.exp3_run)
  exp3_matrix.py                          # make exp3-all: warm-up, matrix, resume, DRY_RUN
  exp3_summary.py                         # make summary
  observe_load.py                         # make observe-load: light keyed and naive bookings for the overlay's dashboard
  k6/
    exp3.js                               # load script
results/                                  # protected; written only by harness scripts
  exp3/
    runs.csv
    summary.csv
    host.json
    raw/
      *.json                              # <stack>_<variant>_f<fault>_r<run>.json from k6, committed as evidence
figures/
  exp3_duplicates.py                      # make chart; --input (default results/exp3/summary.csv), --output
  exp3_duplicates.svg                     # generated by make chart
  tests/
    test_exp3_duplicates.py               # runs exp3_duplicates.py as a subprocess on the fixture, into tmp_path
    fixtures/
      exp3_summary_synthetic.csv          # labelled synthetic
stacks/
  python/
    Dockerfile                            # stages build, unit, arch, runtime (python:3.14-slim)
    .dockerignore
    pyproject.toml                        # package booking; dependencies pinned with ==; pytest config
    importlinter.toml                     # verbatim copy of the Python template
    src/
      booking/
        __init__.py
        domain/
          __init__.py
          booking.py                      # Booking, Charge (frozen dataclasses), DepositAmount
          errors.py                       # InvalidDepositError
        application/
          __init__.py
          ports/
            __init__.py
            inbound.py                    # use-case Protocols, BookSessionCommand, BookingConfirmation, outcomes
            outbound.py                   # BookingStore, BookingTransaction (Protocol), StoredKey, KeyAlreadyClaimedError
          services/
            __init__.py
            request_hash.py               # request_hash(command) -> str
            book_session_naive.py         # BookSessionNaiveService
            book_session_idempotent.py    # BookSessionIdempotentService
        adapters/
          __init__.py
          inbound/
            __init__.py
            http/
              __init__.py
              schemas.py                  # BookingRequest, BookingResponse, ErrorResponse (Pydantic, extra="forbid")
              routes_naive.py             # POST /naive/bookings
              routes_v2.py                # POST /v2/bookings
              health.py                   # GET /health
              fault_hook.py               # FaultHook
              error_handlers.py           # invalid body -> 400 invalid_request
              metrics.py                  # outcome counter (created, replayed, conflict, in-flight)
            mcp/                          # (optional) P6 only
              __init__.py
              schemas.py                  # tool input model (Pydantic, extra="forbid")
              tools.py                    # book_session tool
          outbound/
            __init__.py
            postgres/
              __init__.py
              pool.py                     # connection pool from settings
              booking_store.py            # PostgresBookingStore, PostgresBookingTransaction; 23505 -> KeyAlreadyClaimedError
        bootstrap/
          __init__.py
          settings.py                     # DATABASE_URL, DB_SCHEMA, STACK, DB_POOL_SIZE, FAULT_INJECTION, FAULT_HOLD_MS
          container.py                    # builds the store, services and fault hook
          telemetry.py                    # OTel SDK setup (off unless the observability overlay enables it)
          main.py                         # create_app() factory for uvicorn
    tests/
      unit/
        fakes.py                          # InMemoryBookingStore
        test_domain.py
        test_request_hash.py
        test_book_session_naive.py
        test_book_session_idempotent.py
  java/
    Dockerfile                            # stages build, unit, arch, runtime (Maven on Temurin 25)
    .dockerignore
    pom.xml                               # booking-parent: groupId work.rajc, packaging pom, five modules, Spring Boot BOM, Java 25
    booking-domain/
      pom.xml                             # no dependencies except test scope
      src/main/java/work/rajc/booking/domain/
        Booking.java
        Charge.java
        DepositAmount.java
        InvalidDepositException.java
      src/test/java/work/rajc/booking/domain/
        DepositAmountTest.java
    booking-application/
      pom.xml                             # booking-domain only, plus test scope
      src/main/java/work/rajc/booking/application/port/in/
        BookSessionNaiveUseCase.java
        BookSessionIdempotentUseCase.java
        BookSessionCommand.java           # record
        BookingConfirmation.java          # record
        BookingOutcome.java               # sealed interface with records Created, Replayed, Conflict, InFlight
      src/main/java/work/rajc/booking/application/port/out/
        BookingStore.java
        BookingTransaction.java
        StoredKey.java                    # record
        KeyAlreadyClaimedException.java
      src/main/java/work/rajc/booking/application/service/
        BookSessionNaiveService.java
        BookSessionIdempotentService.java
        RequestHash.java
      src/test/java/work/rajc/booking/application/service/
        InMemoryBookingStore.java
        BookSessionNaiveServiceTest.java
        BookSessionIdempotentServiceTest.java
        RequestHashTest.java
    booking-adapter-in-http/
      pom.xml                             # booking-application, spring-boot-starter-web
      src/main/java/work/rajc/booking/adapter/in/http/
        BookingController.java            # POST /v2/bookings
        NaiveBookingController.java       # POST /naive/bookings
        HealthController.java             # GET /health
        BookingRequest.java               # record
        BookingResponse.java              # record
        ErrorResponse.java                # record
        FaultHook.java
        ApiExceptionHandler.java          # invalid body -> 400 invalid_request
    booking-adapter-out-postgres/
      pom.xml                             # booking-application, spring-boot-starter-jdbc, jackson-databind (stored result jsonb), postgresql
      src/main/java/work/rajc/booking/adapter/out/postgres/
        PostgresBookingStore.java         # TransactionTemplate; SQLSTATE 23505 -> KeyAlreadyClaimedException
        PostgresBookingTransaction.java
    booking-bootstrap/
      pom.xml                             # every module; spring-boot-maven-plugin; test scope archunit-junit5
      src/main/java/work/rajc/booking/bootstrap/
        BookingApplication.java           # @SpringBootApplication(scanBasePackages = "work.rajc.booking")
        UseCaseConfiguration.java         # @Bean wiring of services to ports
      src/main/resources/
        application.yaml                  # port 8080, datasource, Hikari pool 20, fault settings
      src/test/java/work/rajc/booking/architecture/
        HexagonalArchitectureTest.java    # verbatim copy of the Java template
  dotnet/
    Dockerfile                            # stages build, unit, arch, runtime (sdk:10.0, aspnet:10.0)
    .dockerignore
    global.json                           # pins the .NET 10 SDK
    Rajc.Bookings.slnx                    # every project below
    Directory.Build.props                 # net10.0, Nullable enable, ImplicitUsings disable
    Directory.Packages.props              # central package versions
    src/
      Rajc.Bookings.Domain/
        Rajc.Bookings.Domain.csproj       # Microsoft.NET.Sdk, no references
        Booking.cs
        Charge.cs
        DepositAmount.cs
        InvalidDepositException.cs
      Rajc.Bookings.Application/
        Rajc.Bookings.Application.csproj  # Microsoft.NET.Sdk, references Domain only
        Ports/
          Inbound/
            IBookSessionNaive.cs
            IBookSessionIdempotent.cs
            BookSessionCommand.cs
            BookingConfirmation.cs
            BookingOutcome.cs             # abstract record with Created, Replayed, Conflict, InFlight
          Outbound/
            IBookingStore.cs
            IBookingTransaction.cs
            StoredKey.cs
            KeyAlreadyClaimedException.cs
        Services/
          BookSessionNaiveService.cs
          BookSessionIdempotentService.cs
          RequestHash.cs
      Rajc.Bookings.Adapters.Inbound.Http/
        Rajc.Bookings.Adapters.Inbound.Http.csproj  # Microsoft.NET.Sdk.Web, references Application
        BookingEndpoints.cs               # POST /v2/bookings
        NaiveBookingEndpoints.cs          # POST /naive/bookings
        HealthEndpoints.cs                # GET /health
        BookingRequest.cs
        BookingResponse.cs
        ErrorResponse.cs
        FaultHook.cs
        InvalidRequestHandling.cs         # invalid body -> 400 invalid_request
      Rajc.Bookings.Adapters.Outbound.Postgres/
        Rajc.Bookings.Adapters.Outbound.Postgres.csproj  # Microsoft.NET.Sdk, references Application, Npgsql
        PostgresBookingStore.cs           # SQLSTATE 23505 -> KeyAlreadyClaimedException
        PostgresBookingTransaction.cs
      Rajc.Bookings.Bootstrap/
        Rajc.Bookings.Bootstrap.csproj    # Microsoft.NET.Sdk.Web, references Application and both adapters
        Program.cs                        # host on port 8080, endpoint mapping
        ServiceRegistration.cs            # wires services to ports
        appsettings.json
    tests/
      Rajc.Bookings.Application.Tests/
        Rajc.Bookings.Application.Tests.csproj
        InMemoryBookingStore.cs
        DepositAmountTests.cs
        BookSessionNaiveServiceTests.cs
        BookSessionIdempotentServiceTests.cs
        RequestHashTests.cs
      Rajc.Bookings.ArchitectureTests/
        Rajc.Bookings.ArchitectureTests.csproj  # references every src project; NetArchTest.Rules, xunit
        HexagonalArchitectureTests.cs     # verbatim copy of the .NET template
```
<!-- structure:end -->

## Naming conventions (checked)

- **Python:** PEP 8. Modules and packages lowercase_with_underscores, classes CapWords, exceptions
  end in `Error`, every package has `__init__.py`.
- **Java:** packages lowercase letters and digits, folders exactly mirror packages under
  `src/main/java` or `src/test/java`, classes UpperCamelCase, exceptions end in `Exception`, no `I`
  prefix on interfaces. Module folder = artifactId, lowercase and hyphenated.
- **.NET:** PascalCase files and folders; namespace = project name + folder path; interfaces start
  with `I`; exceptions end in `Exception`. Folder = project = assembly = root namespace. Only the HTTP
  adapter and Bootstrap use `Microsoft.NET.Sdk.Web`. The root is `Rajc.Bookings` (plural), so it
  never collides with the `Booking` type.

## BDD standards (checked)

Feature files live in `bdd/features/`, step definitions in `bdd/steps/`, and nothing else lives under
`bdd/`. `check_hexagonal.py bdd` (and `--all`) enforces, for every feature file:

- Exactly one `Feature`; a `Background` holds context only (`Given` steps).
- Each scenario has 3 to 7 steps and exactly one action: one `When` (an `And` or `But` after it is
  another action). Steps run `Given`, then `When`, then `Then`, and end in an observable outcome.
- Every `Scenario Outline` has `Examples`; use one instead of copying a scenario for each value.
- Every scenario carries a traceability tag on itself, its `Rule` or its `Feature`: `@spec-...`
  (spec section), `@contract-<n>` (contract test) or `@rule-<id>` (a rule below).

Not checked, but expected: steps in domain language rather than HTTP or SQL; scenarios that do not
depend on each other; step definitions that are one call into a driver over the repo's code. Tag a
scenario or an `Examples` table `@known-defect` while the defect it describes is unfixed: `make bdd`
runs it as a strict expected failure, so the fix shows up as a failure until the tag is removed.

## Commands (keep these working)

| Command | Does |
| --- | --- |
| `make doctor` | Checks Docker or Podman, k3d, kubectl, k6, jq, Python 3.12+; creates `.venv` from requirements-host.txt |
| `make up` / `make down` | Creates or deletes the k3d cluster with Postgres and all stacks |
| `make deploy STACK=<stack>` | Builds the runtime image, imports it into k3d, rolls it out |
| `make unit STACK=<stack>` | Runs the stack's unit tests (container stage `unit`) |
| `make arch STACK=<stack>` | `check_hexagonal.py <stack>` (structure complete) plus the architecture tests (container stage `arch`) |
| `make contract STACK=<stack>` | Runs contracts/tests against one stack |
| `make bdd` | `check_hexagonal.py bdd` (BDD standards) plus the scenarios in `bdd/steps`; `@known-defect` ones are strict expected failures |
| `make exp3 STACK= VARIANT= FAULT= RUN=` | One measured run; appends a row to results/exp3/runs.csv |
| `make exp3-all` / `make summary` / `make chart` | Full matrix, summary.csv, figures/exp3_duplicates.svg |
| `make mesh-up` | Installs the opt-in Istio ambient overlay (off for measured runs) |
| `make observe-up` | Installs the opt-in OpenTelemetry overlay (off for measured runs) |
| `make observe-load [STACK=] [MINUTES=5]` | Light keyed, replayed, conflicting and naive bookings on every running stack (or STACK) so the overlay's panels have data; writes nothing to results/ |

## Rules (the naive baseline is exempt from G2 only)

- **G0 Hexagonal architecture.** The layers, folder structure and names above. Architecture tests are
  the templates in `tools/arch/templates/`, copied verbatim; the checker fails if a copy differs. If a
  template does not compile or seems wrong, stop and tell the author.
- **G1 Explicit contracts.** DTOs are explicit types in the inbound adapter (records, Pydantic models
  with `extra="forbid"`). No persistence or driver types in endpoint or tool signatures.
- **G2 Message reliability.** Every mutating endpoint or tool requires an idempotency key, stored in the
  same transaction as its side effect, with the replay and conflict behaviour in the spec.
- **G3 One transaction per use case**, through the BookingStore port. No network calls inside a transaction.
- **G4 Async only for waiting.** No CPU-heavy or blocking work on an event loop or in async handlers.
- **G5 Events and callbacks** (later posts): one-way delivery, short handlers, no locks across a call out.
- **G6 Chunky contracts.** One call per use case. No property-like endpoints exposing internal state.
- **G7 No real money, no real secrets.** Charges are rows; credentials are labelled local defaults.
- **G8 Same behaviour in every stack.** Change a stack to pass a contract test, never the test.

`POST /naive/bookings` is the control group (`book_session_naive.py`, `routes_naive.py`,
`BookSessionNaiveService`, `NaiveBookingController`, `NaiveBookingEndpoints`): no keys, deduplication,
retries, locks or unique constraints. `.claude/rules/naive-baseline.md` repeats this.

## Honesty rules

- **H1** Never invent, estimate or hand-edit numbers. A hook blocks edits to `results/`, `observations/`,
  `CLAUDE.md`, `.claude/` and `tools/arch/`.
- **H2** Report failures plainly with the command and its output. Never claim something works unrun.
- **H3** Never silently change the spec, tests, tooling, versions or folder structure, and never weaken
  an architecture test. Do not switch from k3d to docker compose without approval.
- **H4** Synthetic test data lives only in the fixtures folders listed above, labelled synthetic.

## Working style

- Plan first for any task spanning more than one directory; wait for approval.
- For each stack: create every file in its part of the tree (stubs are fine), copy its architecture
  test, prove `make arch` fails on one deliberate violation, revert, then fill in from the inside out.
- Verify versions, image tags and APIs from registries and official docs; record them in `versions.md`.
- Small commits with conventional messages. If the same step fails twice, stop and report.

## Definition of done for any task

- `python3 tools/arch/check_hexagonal.py --all` passes (layers, naming, no files outside the tree, the
  BDD standards in `bdd/`, and `AGENTS.md` carrying this tree verbatim). A
  Stop hook runs it whenever you try to finish and blocks you once if it fails; fix the code, never the check.
  Before publishing, `--all --complete` must also pass: every listed, non-optional file exists.
- `make arch` (which also requires every listed file of the stack to exist) and `make contract` pass for
  every stack you touched, and you showed the output.
- `versions.md` matches what is built. No edits to protected paths; no unreported TODOs.
