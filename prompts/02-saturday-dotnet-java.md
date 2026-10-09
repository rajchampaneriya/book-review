# P2. .NET 10 and Spring Boot stacks

**When:** Sat 10 Oct, 08:00 to 12:00 IST.
**Session:** a new Claude Code session at the repo root, in plan mode.

## Prompt (paste as is)

```text
Read CLAUDE.md and docs/exp3-spec.md first. The FastAPI stack, the contract tests and the harness are done; treat them as the reference, including their hexagonal structure. The CLAUDE.md tree is the whole repository: create every file it lists and nothing else. If you need a file it does not list, stop and ask me.

Task: add stacks/dotnet and stacks/java with every file in the .NET and Java trees in CLAUDE.md, with exactly those names and nothing else, so both pass make unit, make arch and the same contract tests, and run under the same harness, unchanged. Builds and tests run in containers through each Dockerfile's stages build, unit, arch and runtime; the host has no JDK or .NET SDK. Each service listens on 8080 in its container.
- stacks/dotnet: the Rajc.Bookings.* projects from CLAUDE.md. .NET 10 minimal API in the HTTP adapter, Npgsql with plain SQL in the Postgres adapter, record DTOs. Only the HTTP adapter and Bootstrap use the Web SDK. Copy tools/arch/templates/dotnet/HexagonalArchitectureTests.cs verbatim to tests/Rajc.Bookings.ArchitectureTests/, referencing every src project plus NetArchTest.Rules and xunit.
- stacks/java: Maven multi-module from CLAUDE.md, base package work.rajc.booking, folders mirroring packages. Spring Boot 4.1.x on Java 25; Spring only in the adapters and bootstrap; JdbcClient and HikariCP in the Postgres adapter; transactions via TransactionTemplate inside PostgresBookingStore, never @Transactional in application code. Copy tools/arch/templates/java/HexagonalArchitectureTest.java verbatim to booking-bootstrap/src/test/java/work/rajc/booking/architecture/, with test-scoped archunit-junit5. Keep the default platform-thread Tomcat for this experiment.
- make arch STACK=dotnet runs check_hexagonal.py dotnet, then builds the arch stage, which runs dotnet test tests/Rajc.Bookings.ArchitectureTests. make arch STACK=java runs check_hexagonal.py java, then builds the arch stage, which runs the mvn command in the spec. check_hexagonal.py fails if a listed file is missing or an unlisted file exists.

Constraints:
- Same ports, use cases, outcomes (Replayed, Conflict, InFlight), contract, status codes, headers, error bodies and request-hash definition as the Python stack and the spec.
- Same resource limits and a 20-connection database pool. Record the thread and pool configuration in versions.md.
- Do not change contracts/tests, the harness or tools/arch (templates included) to make a stack pass. If a template does not compile or run, stop and tell me.
- Verify image tags and package versions from the registries; record them in versions.md.

For each stack, work in this order: skeleton with every listed file (stubs are fine) and the copied architecture test; prove make arch fails on one deliberate violation (an application service referencing the Postgres adapter), then revert; domain, ports and services with unit tests using an in-memory BookingStore; adapters; bootstrap.

Plan first: the files per stack matched line by line against the CLAUDE.md tree (there should be no deviation), packages and versions, the port interfaces, and how each Postgres adapter maps SQLSTATE 23505 to KeyAlreadyClaimedException. Wait for my approval. Then build .NET first, then Java.

Done when, for both stacks: python3 tools/arch/check_hexagonal.py --all, make unit, make arch, make deploy, make contract and one make exp3 run per variant at FAULT=0.05 succeed. Show me the output and the runs.csv rows. Commit per stack. Do not push.
```

## Your review checklist

Architecture:

- [ ] `python3 tools/arch/check_hexagonal.py --all` passes; `make arch` passes for dotnet (6 facts) and java (5 rules).
- [ ] Nothing "not in" or "missing from the folder structure": no `mvnw`, `NuGet.config`, extra module,
      project or helper class, and no listed file left as an empty stub.
- [ ] Both architecture tests are unmodified copies of their templates.
- [ ] Each stack's commit history shows its deliberate violation failing `make arch`, then reverted.
- [ ] Java: folders mirror packages; booking-domain and booking-application poms have no non-test dependencies besides inner booking modules; no `@Transactional` or Spring type in `..application..`.
- [ ] .NET: namespaces equal project name plus folder path; Domain and Application use `Microsoft.NET.Sdk` with no package references; no Npgsql type in Application.
- [ ] Controllers and endpoints depend on driving-port interfaces, never on `*Service` classes.

Behaviour:

- [ ] Both stacks reject unknown JSON fields with 400 `invalid_request`.
- [ ] The request hash uses the spec's newline-joined string, not serialised JSON.
- [ ] Java maps SQLState 23505 to `KeyAlreadyClaimedException` rather than catching every exception.
- [ ] .NET uses `await Task.Delay` and Java `Thread.sleep` in the fault hook, and only when enabled.
- [ ] Pool size is 20 in both; versions.md says so.
