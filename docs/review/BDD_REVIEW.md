# BDD review — rajchampaneriya/book-review

Commit `ac41f49` (10 Oct 2026), reviewed 15 Oct 2026. Every claim cites a file and line in the repo. Anything I could not verify from a file or a run is marked **assumption**.

## 1. What exists today

The repo has **no `.feature` files, no step definitions and no Given/When/Then tests**. The nearest thing to an executable specification is the cross-stack contract suite, which I audited as the acceptance layer. I also audited the unit tests, because they encode the idempotency policy.

| Suite | Files | Style | Run here? |
| --- | --- | --- | --- |
| Contract tests 1–8 (acceptance) | `contracts/tests/*.py` (5 files, 8 test functions, 17 cases once parametrised) | pytest + httpx + psycopg, imperative | No: needs the k3d cluster |
| Python unit tests | `stacks/python/tests/unit/*.py` | pytest, arrange-act-assert | **Yes: 20 passed** (Python 3.14.6, copy of the stack) |
| .NET unit tests | `stacks/dotnet/tests/Rajc.Bookings.Application.Tests/*.cs` | xUnit, AAA | No: no .NET SDK here |
| Java unit tests | `stacks/java/booking-*/src/test/**/*.java` | JUnit 5, AAA | No: JDK 21 only and Maven Central unreachable from this sandbox |
| Figure test | `figures/tests/test_exp3_duplicates.py` | pytest subprocess | **Yes: 1 passed** |
| Architecture gate self-test | `tools/arch/selftest.py` | 114 outcome-named cases | **Yes: 114/114** |
| Harness (`harness/*.py`, `harness/k6/exp3.js`) | none | — | — |

## 2. Scorecard against your BDD standards

✔ meets · ◐ partly · ✘ does not · — not applicable

| Standard | Contract tests | Unit tests (3 stacks) | Figure test | Harness |
| --- | --- | --- | --- | --- |
| Domain language, declarative | ◐ titles are behavioural; bodies are HTTP verbs, headers and SQL | ◐ | ✘ | — no tests |
| One behaviour per scenario, title states the outcome | ✔ | ◐ two titles promise more than they test (B8, B10) | ✔ | — |
| Given = context, When = one action, Then = observable outcome | ◐ implicit | ◐ implicit AAA | ◐ | — |
| Short (3–7 steps) | ✔ | ✔ | ✔ | — |
| Background only for shared context | ✘ a fixture truncates shared tables before every test (B6) | ✔ | ✔ | — |
| Outline/Examples for data variations | ✔ `test_validation.py` | ✔ Theory / ParameterizedTest / parametrize | — | — |
| Independent, no ordering or shared state | ✘ shared schema; timing test runs first (B2, B6) | ✔ | ✔ | — |
| Thin, reusable steps delegating to domain code | ◐ `conftest.py` helpers are a good start | — | — | — |
| Happy + edge + failure coverage | ◐ happy ✔, edge ◐, failure ◐; no fault-on path | ◐ no mid-transaction failure | ◐ happy only | ✘ |
| Traceable to an experiment or requirement | ✔ docstrings use the spec's numbering | ✘ | ✔ | ✘ |

**BDD coverage used to shade the diagram's Experiment Map:** Full for the architecture gate only; Partial for both arms in all three stacks, the fault hook, the contract suite, the unit tests and the chart; None for the run, matrix and summary harness, P0 and everything only referenced (P6, post 2, post 4, G5).

## 3. Findings, with before and after

Severity is about what a gap lets through, not about style.

### B1 · High — There is no executable specification layer (repo-wide)

**Where:** no `*.feature` anywhere; the eight behaviours of `docs/exp3-spec.md:179-191` exist only as pytest code in `contracts/tests/`.

**Why it matters:** the experiment's claim is "same behaviour in every stack" (CLAUDE.md rule G8). Today that claim is defined by Python test code that an article reader, or a reviewer of the Java and .NET stacks, has to reverse-engineer. A Gherkin layer makes the eight behaviours, plus the gaps below, readable in business terms and runnable against every stack from one source.

**After:** the eight new feature files in `bdd/features/` (37 scenarios, parsed by the official Gherkin parser and linted for 3–7 steps, exactly one `When`, Given→When→Then order and a traceability tag on every scenario; 0 lint problems). Section 6 shows thin step definitions running some of them against the real code.

> Update: the CLAUDE.md tree now lists `bdd/`, `docs/review/` and `TASKS.md` as optional entries, so these files pass the structure gate; `pytest-bdd` 9.0.0 is pinned in `requirements-host.txt` and `versions.md`; `make bdd` runs the steps; and `check_hexagonal.py` enforces the standards above on every feature file.

### B2 · High — The fault hook's "on" path, which the whole experiment depends on, has no test, and the "off" test is order- and timing-sensitive

**Where:** `contracts/tests/test_fault_hook.py:4-17`

```python
def test_fault_header_is_ignored_when_injection_is_disabled(client, clean_schema):
    response = client.post(
        "/v2/bookings",
        json={ "client_ref": "fault-off", ... "deposit_cents": 2500 },
        headers={"Idempotency-Key": "fault-off-1", "X-Fault": "hold-after-commit"},
    )
    assert response.status_code == 201
    assert response.elapsed.total_seconds() < 0.5
```

**Why it's a problem:**
- Only the disabled path is tested. Nothing checks that, when enabled, the hook holds the response **after** the commit, which is the mechanism that produces every duplicate the experiment measures (`docs/exp3-spec.md:108-119`).
- pytest collects `test_fault_hook.py` first (alphabetical order), so this is the first `/v2/bookings` request a freshly deployed stack serves. A cold JVM or .NET JIT could push it past 500 ms (**assumption**: not measured; the readiness probe only warms `/health`, `infra/k8s/java.yaml:41-46`).
- `Then` checks status and time, not the business outcome (that a booking exists).
- The body is inlined instead of using `booking_body()` from `conftest.py:68-75`.

**After** (`bdd/features/exp3_fault_injection.feature`):

```gherkin
Background:
  Given the booking service for the stack under test has served a warm-up booking

@contract-8 @happy
Scenario: The fault header is ignored while injection is disabled
  Given fault injection is disabled on the stack under test
  When the client books with the hold-after-commit fault header
  Then the confirmation arrives in under 500 ms
  And exactly one booking exists for that request

@fault-injection @happy
Scenario: The fault header holds the confirmation after the booking commits
  Given fault injection is enabled with a 2000 ms hold
  When the client books with the hold-after-commit fault header
  Then the booking is recorded before the confirmation arrives
  And the confirmation arrives no sooner than 2000 ms after the request
```

### B3 · Medium — The request-key rules are tested only for "missing", and the refusal doesn't check that nothing was written

**Where:** `contracts/tests/test_v2_bookings.py:9-12`

```python
def test_missing_key_is_rejected(client, clean_schema):
    response = client.post("/v2/bookings", json=booking_body("v2-nokey"))
    assert response.status_code == 400
    assert response.json() == {"error": "idempotency_key_required"}
```

**Why it's a problem:** the spec allows 1 to 255 printable ASCII characters (`docs/exp3-spec.md:83-84`), and each stack implements that check by hand (`routes_v2.py:29-35`, `BookingEndpoints.cs:65-80`, `BookingController.java:51-62`). Empty, 256-character, space and non-ASCII keys, and the 255-character boundary, are never exercised, so a drift in any one stack would go unnoticed. The test also never checks that no booking was written.

**After** (`bdd/features/exp3_idempotent_booking.feature`):

```gherkin
@contract-3 @failure
Scenario Outline: A booking without a usable request key is refused
  When the client books with <key>
  Then the booking is refused because a request key is required
  And no booking or charge is recorded for that client reference

  Examples:
    | key                                         |
    | no request key                              |
    | an empty request key                        |
    | a 256-character request key                 |
    | a request key containing a space            |
    | a request key containing a non-ASCII letter |

@edge
Scenario: The longest permitted request key is accepted
  When the client books with a 255-character request key
  Then the client receives a new booking confirmation
  And exactly one booking and one deposit charge exist for that request
```

### B4 · Medium — The conflict test changes one field and checks bookings but not charges

**Where:** `contracts/tests/test_v2_bookings.py:31-44`

```python
first = client.post("/v2/bookings", json=booking_body("v2-conflict", deposit_cents=2500), ...)
second = client.post("/v2/bookings", json=booking_body("v2-conflict", deposit_cents=9999), ...)
...
assert c["bookings_total"] == 1
```

**Why it's a problem:** the request hash covers five fields (`docs/exp3-spec.md:85-86`). Only `deposit_cents` is varied, so a stack that dropped, say, `owner_id` from its hash would pass. The double-charge risk is the point of the experiment, but `charges_total` is not asserted.

**After:**

```gherkin
@contract-5 @failure
Scenario Outline: Reusing a request key for a different booking is refused as a conflict
  Given the client has booked session "s-42" with a fresh request key
  When the client books again with the same request key but a different <detail>
  Then the booking is refused as a request-key conflict
  And still exactly one booking and one deposit charge exist for that request key

  Examples:
    | detail           |
    | client reference |
    | session          |
    | dog              |
    | owner            |
    | deposit amount   |
```

### B5 · Low — The replay and concurrency tests are imperative; the concurrency test misses one observable

**Where:** `contracts/tests/test_v2_bookings.py:15-28` and `47-64`

```python
first = client.post("/v2/bookings", json=body, headers={"Idempotency-Key": "replay-1"})
second = client.post("/v2/bookings", json=body, headers={"Idempotency-Key": "replay-1"})
assert second.headers.get("Idempotent-Replayed") == "true"
```

**Why it's a problem:** these are good behaviours with clear titles, but headers, status codes and asyncio plumbing sit in the test body, which makes them hard to read as business rules or reuse. The concurrency test checks that all 20 responses share a booking id but not that exactly one was *not* a replay, which is what proves one request did the work.

**After:**

```gherkin
@contract-4 @happy
Scenario: Retrying with the same request key replays the original confirmation
  Given the client has booked session "s-42" with a fresh request key
  When the client retries the identical booking with the same request key
  Then the client receives the original confirmation marked as a replay
  And exactly one booking and one deposit charge exist for that request

@contract-6 @edge
Scenario: Twenty simultaneous duplicates produce exactly one booking
  When 20 identical bookings with the same fresh request key arrive at the same time
  Then all 20 clients receive the same booking confirmation
  And exactly one of those confirmations is not marked as a replay
  And exactly one booking and one deposit charge exist for that request
```

### B6 · High — Every contract test truncates the shared tables, so tests are coupled to each other and to any measurement in progress

**Where:** `contracts/tests/conftest.py:39-45`, used by every behavioural test; global counts in `conftest.py:48-65`

```python
@pytest.fixture()
def clean_schema(db):
    with db.cursor() as cur:
        cur.execute(f"TRUNCATE {STACK}.bookings, {STACK}.charges, {STACK}.idempotency_keys")
```

**Why it's a problem:**
- Tests share one mutable schema, so they cannot run in parallel, and each assertion counts the whole table rather than its own request.
- `harness/exp3_run.py:58` uses the same schema. Running `make contract` during `make exp3` or `make exp3-all` truncates the tables of the run being measured, and nothing stops it. That corrupts `results/` silently.

**After:** each scenario creates its own `client_ref` and key (for example a uuid4), and a small read model counts **by client reference**, so no truncate is needed:

```python
# contracts/support/ledger.py (proposed)
def for_client_ref(db, schema, client_ref) -> Ledger:
    """bookings, charges and stored keys for one client reference."""
```

```gherkin
Then exactly one booking and one deposit charge exist for that request
```

### B7 · Medium — Validation is parametrised well, but it skips exactly the inputs where the stacks disagree

**Where:** `contracts/tests/test_validation.py:7-21`

```python
INVALID_BODIES = {
    "missing field": ..., "unknown field": ..., "negative deposit": ...,
    "zero deposit": ..., "wrong type": {**booking_body("v"), "deposit_cents": "2500"},
}
```

**What's good:** this is an Outline in all but name, and it runs every case against both endpoints.

**Why it's still a problem (rule G8):** reading the three adapters shows different behaviour for inputs the table omits:

| Input | python | dotnet | java | Evidence |
| --- | --- | --- | --- | --- |
| `"client_ref": ""` | accepted (201) | 400 | accepted (201) | `schemas.py:11-14`; `NaiveBookingEndpoints.cs:55-58`; `NaiveBookingController.java:40-42` |
| field names in another case (`CLIENT_REF`) | 400 | **accepted** | 400 | `InvalidRequestHandling.cs:21` sets `PropertyNameCaseInsensitive = true` |
| `"deposit_cents": 2500.5` | 400 (`Field(strict=True)`, `schemas.py:15`) | 400 | **assumption:** likely truncated to 2500 by Jackson's default float-to-int coercion; only string coercion is disabled (`UseCaseConfiguration.java:49-54`) | verify with a test |
| bad body **and** no key on `/v2` | `invalid_request` | **`idempotency_key_required`** | `invalid_request` | `.NET` checks the key before reading the body (`BookingEndpoints.cs:22-32`); FastAPI and Spring bind the body first |

None of the assertions check that nothing was recorded.

**After** (`bdd/features/exp3_booking_request_validation.feature`); the second Examples table is tagged `@open-question` because the spec doesn't settle these cases:

```gherkin
Scenario Outline: A malformed booking is refused and nothing is recorded
  When the client sends a <endpoint> booking with <defect>
  Then the request is refused as invalid
  And no new booking or charge is recorded

  Examples: Covered today by contracts/tests/test_validation.py
    | endpoint | defect                     |
    | naive    | the owner missing          |
    ...
  @open-question
  Examples: Not covered today; stacks are likely to disagree
    | endpoint | defect                         |
    | keyed    | an empty client reference      |
    | keyed    | a fractional deposit of 2500.5 |
    | keyed    | field names in upper case      |
    ...
```

### B8 · High — "Failed transaction leaves nothing behind" never fails a transaction part-way (all three stacks)

**Where:** `stacks/python/tests/unit/test_book_session_idempotent.py:74-83`; `BookSessionIdempotentServiceTest.java:72-84`; `BookSessionIdempotentServiceTests.cs:72-84`

```python
def test_failed_transaction_leaves_nothing_behind():
    async def scenario():
        store = InMemoryBookingStore()
        store.keys["k1"] = StoredKey("k1", request_hash(command()), None)
        await BookSessionIdempotentService(store).book("k1", command())
        assert store.bookings == []
```

**Why it's a problem:** the context and action are identical to the in-flight test a few lines above (`:62-71`; Java `:60-70`; .NET `:59-70`). The claim fails at the first statement, so there is no partial write to roll back. The title promises atomicity (rule G3), but the scenario only re-tests "in flight". A regression where the booking is written and the charge fails would pass.

**After** (`bdd/features/exp3_idempotency_policy.feature`), **executed against the Python service in section 6 and passing:**

```gherkin
@unit @failure @atomicity @rule-G3
Scenario: A booking that fails part-way leaves no trace
  Given recording the deposit charge will fail once
  When the service books with request key "k1"
  Then the booking fails
  And no booking, no charge and no claim on request key "k1" remain

@unit @failure @atomicity @rule-G3
Scenario: A request key from a failed attempt can be used again
  Given an earlier booking with request key "k1" failed part-way
  When the service books with request key "k1"
  Then the outcome is a new booking
  And exactly one booking and one deposit charge exist for request key "k1"
```

The in-memory store only proves the service doesn't swallow the error. The real guarantee lives in each Postgres adapter, so run the same two scenarios against Postgres too, for example in the contract stage.

### B9 · Medium — The in-flight outcome is never exercised at the HTTP boundary

**Where:** mapping in `routes_v2.py:66-71`, `BookingEndpoints.cs:42-46`, `BookingController.java:42`; the k6 client retries 409 (`harness/k6/exp3.js:75`); .NET logs the anomaly with `Trace.WriteLine` (`BookSessionIdempotentService.cs:63`).

**Why it's a problem:** the contract tests can't produce `InFlight`, so the 409 + `Retry-After: 1` mapping, and the "logged as a bug" requirement (`docs/exp3-spec.md:100-101`), are unverified in all three stacks. `Trace.WriteLine` goes to trace listeners, not to ASP.NET Core logging, so it most likely never reaches the container log (**assumption**).

**After:**

```gherkin
@adapter @inflight
Scenario: An in-flight outcome tells the client to retry after one second
  Given the booking use case will report request key "k1" as in flight
  When the client books with request key "k1"
  Then the client is told the booking is still in flight and to retry after 1 second
  And the in-flight anomaly appears in the service log
```

### B10 · Low — A test title claims immutability it doesn't check

**Where:** `stacks/java/booking-domain/src/test/java/work/rajc/booking/domain/DepositAmountTest.java:27-35`

```java
@Test
void bookingAndChargeAreImmutable() {
    ...
    assertNotEquals(booking, other); // a copied booking with a different deposit is a new value
    assertEquals(2500, charge.amountCents()); // records expose no setters
}
```

**Why it's a problem:** it asserts record equality and a getter, which the language guarantees. The title states an outcome the body doesn't test, and it lives in `DepositAmountTest`, so it's hard to trace. The .NET twin (`DepositAmountTests.cs:26-39`) has the same placement.

**After:** delete it (Java records and C# records are immutable by construction), or rename it to what it checks (`aBookingWithADifferentDepositIsADifferentValue`) and move it to a `BookingTest`. No Gherkin is needed: this is a language property, not a behaviour.

### B11 · Low — Python unit tests hide Given/When/Then in async boilerplate

**Where:** `stacks/python/tests/unit/test_book_session_idempotent.py:20-32` (the same pattern in every test)

```python
def test_first_call_creates_one_booking_and_one_charge():
    async def scenario():
        store = InMemoryBookingStore()
        service = BookSessionIdempotentService(store)
        outcome = await service.book("k1", command())
        assert isinstance(outcome, Created)
        ...
    asyncio.run(scenario())
```

**After:** the policy feature with thin steps (section 6), or plain tests with `# given / # when / # then` and a shared `book()` helper. The steps in section 6 wrap `asyncio.run` once, in the driver.

### B12 · Critical — The harness has no tests, and that is how 36 of 54 runs became invalid

**Where:** `harness/exp3_matrix.py:115-121`, `harness/exp3_run.py:75-81`, `harness/exp3_summary.py:36-38`, `harness/hostinfo.py:36`; evidence in `results/exp3/runs.csv` and `results/exp3/host.json`.

```python
for stack in STACKS:
    if stack not in warmups:
        continue
    for other in STACKS:
        if other != stack:
            scale(other, 0)          # the stack under test is never scaled back to 1
    warm_up(stack)
```

**Why it's critical:**
- The matrix scales the other stacks to 0 but never scales the stack under test back to 1. After the .NET pass, Java and Python are both at 0 replicas when their turn comes. All 36 Java and Python rows for commit `c433bfe` show `bookings_total = 0`, `timeouts = attempts = 3 × logical`, and `lost = logical` (for example `results/exp3/raw/java_naive_f0.05_r1.json`: `http_req_failed` rate 1.0, median duration 999.9 ms against the 1 s timeout).
- `exp3_run.py` appends a row whatever happened, because k6 exits 0 with no thresholds, so the invalid runs were recorded as results.
- `exp3_summary.py` groups every row in `runs.csv` regardless of commit or run length. The committed `summary.csv` predates the matrix and mixes the 500-request smoke run `r9` with a full run (python naive 5%: `runs=2`, median 261 = median(25, 497)). If `make summary` were run on today's `runs.csv`, it would report **0 duplicates per 10k for Java and Python naive at 5%**, because 0 is the median of `{498, 0, 0, 0}`. I computed that in scratch, without writing to `results/`.
- `hostinfo.py:36` formats `platform.machine` without calling it, so `results/exp3/host.json` records `"Darwin 27.0.0 (<function machine at 0x1059dbd70>)"`.

**After:** `bdd/features/exp3_measurement_run.feature` and `bdd/features/exp3_results_summary_and_chart.feature`. **Run against today's code, the matrix outline fails for java and python and passes for dotnet**, which matches the data exactly:

```gherkin
@matrix @regression @failure
Scenario Outline: Only the stack under test serves traffic during its runs
  Given the matrix has finished measuring <earlier>
  When the matrix starts measuring <stack>
  Then <stack> has 1 replica
  And every other stack has 0 replicas

  Examples:
    | earlier      | stack  |
    | no stack yet | dotnet |
    | dotnet       | java   |
    | java         | python |

@run @failure
Scenario: A run in which no booking was recorded is rejected, not appended
  Given the stack under test answers no requests
  When a measured run completes
  Then the run is reported as invalid
  And no row is appended to the run log
```

### B13 · High — The chart test covers one happy path, and the published SVG is the synthetic fixture

**Where:** `figures/tests/test_exp3_duplicates.py:13-30`; `figures/exp3_duplicates.py:60` and `:68`; `figures/exp3_duplicates.svg`

```python
for value in ("98.0", "99.0", "97.0", "497.0", "498.0", "496.0"):
    assert value in svg
```

**Why it's a problem:**
- I regenerated the chart from `figures/tests/fixtures/exp3_summary_synthetic.csv`. Ignoring the date and generated ids, it is **identical** to the committed `figures/exp3_duplicates.svg`. Its "98.0 / 99.0 / 97.0" bars are the fixture's numbers, not measurements, which breaks rule H4. The P3 prompt asked for `make chart` against the fixture (`prompts/03-matrix-summary-chart.md:21`) without an `--output`, so it overwrote the published path; it was then committed in `ac41f49`.
- A missing group is drawn as a real 0 bar labelled `0` (`exp3_duplicates.py:60,68`). Today, Java and Python 1% would read as "no duplicates" rather than "no data".

**After** (both fail on today's code, as they should):

```gherkin
@chart @failure
Scenario: A group with no data is shown as missing, not as zero
  Given a summary with no java rows at a 1% fault rate
  When the chart is drawn
  Then the java 1% bars are labelled "no data"

@chart @failure @rule-H4
Scenario: The synthetic fixture can never become the published chart
  Given the input is the labelled synthetic fixture
  When the chart is drawn to the published chart's location
  Then drawing is refused because the input is synthetic
```

### B14 · Low — Unit and figure tests don't trace to the spec

**Where:** the contract docstrings do this well (`test_health.py:1` "Contract test 1"); the unit tests in all three stacks and the figure test have no link to a spec clause.

**After:** one tag scheme across the features: `@exp3`, `@spec-exp3-L<lines>` for the spec section, `@contract-<n>` for the spec's contract-test number, `@rule-G<n>` / `@rule-H<n>` for CLAUDE.md rules, plus `@happy`, `@edge` or `@failure`. Every scenario in `bdd/features/` carries at least one spec, contract or rule tag (checked by the lint).

### B15 · Low — The same five policy tests are hand-copied in three languages

**Where:** `test_book_session_idempotent.py`, `BookSessionIdempotentServiceTest.java`, `BookSessionIdempotentServiceTests.cs`, and the matching naive tests.

**Why it matters:** rule G8 asks for the same behaviour everywhere, and three copies drift independently. B8 is the same mistake made three times.

**After:** one `bdd/features/exp3_idempotency_policy.feature`, run by pytest-bdd (Python), Cucumber-JVM (Java) and Reqnroll (.NET), each with a thin driver over its own in-memory store. This adds test dependencies to each stack, which must be added to the CLAUDE.md tree and `versions.md` by the author.

## 4. Coverage map after the new features

| Experiment part | Happy | Edge | Failure | Feature file |
| --- | --- | --- | --- | --- |
| Treatment · `/v2/bookings` | create, replay | 255-char key, 20 concurrent | key rules ×5, conflict ×5 fields, lost confirmation | `exp3_idempotent_booking.feature` |
| Idempotency policy (application) | create + stored result | in-flight | mid-transaction failure, key reusable after failure, 409 mapping | `exp3_idempotency_policy.feature` |
| Control · `/naive/bookings` | repeat → 2 bookings | ignores a key | lost confirmation → double charge | `exp3_naive_baseline.feature` |
| Input validation (both endpoints) | — | upper-case fields, null, non-JSON | 10 covered + 6 open-question rows, body-vs-key precedence | `exp3_booking_request_validation.feature` |
| Fault hook | off, on (hold after commit) | unrecognised header value | — | `exp3_fault_injection.feature` |
| Health | names the stack | — | — | `exp3_service_health.feature` |
| Measured runs and matrix | clean start, counting, resume, dry run | deterministic fault selection | 0-replica regression, invalid run refused, host info | `exp3_measurement_run.feature` |
| Summary and chart | median/range, p99 overhead, labels incl. 0 | — | other commits and smoke runs excluded, invalid run refused, missing group, fixture guard | `exp3_results_summary_and_chart.feature` |

## 5. Step-definition design

Steps are one line each and call a **driver** that speaks the domain; drivers call the repo's own code. No policy, SQL or HTTP lives in a step.

```python
@given("recording the deposit charge will fail once")
def charge_fails_once(policy):
    policy.fail_next_charge()

@when(parsers.parse('the service books with request key "{key}"'))
def book(policy, key):
    policy.book(key)

@then(parsers.parse('no booking, no charge and no claim on request key "{key}" remain'))
def no_trace(policy, key):
    assert policy.ledger() == (0, 0)
    assert key not in policy.store.keys
```

`bdd/steps/drivers.py` holds `BookingPolicy` (wraps `BookSessionIdempotentService` and the repo's `InMemoryBookingStore` from `stacks/python/tests/unit/fakes.py`), `MatrixHarness` (runs `harness.exp3_matrix.main()` with kubectl, k6 and the per-run harness faked), `Summary` (runs `harness.exp3_summary.main()` on a run log in `tmp_path`) and `Chart` (runs `figures/exp3_duplicates.py` as a subprocess, like the repo's own test). For the HTTP-level features, the same pattern applies: a `BookingClient` driver over httpx and a `Ledger` read model over psycopg, built from the existing `conftest.py` helpers.

## 6. What I ran

Python 3.14.6 in a scratch virtualenv; the repo was imported read-only (`PYTHONDONTWRITEBYTECODE=1`, no cache), and `git status` stayed clean.

| Command | Result |
| --- | --- |
| `pytest` on a copy of `stacks/python` (unit tests) | 20 passed |
| `pytest figures/tests` (matplotlib 3.11.2) | 1 passed |
| `python3 tools/arch/selftest.py` | 114/114 |
| `python3 tools/arch/check_hexagonal.py --all` | passed |
| `python3 tools/arch/check_hexagonal.py --all --complete` | **failed**: `README.md` missing (CLAUDE.md line 57) |
| Official Gherkin parser + lint over `bdd/features/` | 8 files, 37 scenarios, 0 problems |
| pytest-bdd 9.0.0 over `bdd/steps/` | **5 passed, 4 failed**, as expected (below) |

| Scenario | Result | Meaning |
| --- | --- | --- |
| Policy: fresh key, in-flight, fails part-way, key reusable after failure | 4 passed | the Python service's policy is sound at the application level |
| Matrix: only the stack under test serves — dotnet | passed | first stack in the loop is fine |
| Matrix: only the stack under test serves — java, python | **failed**: "java had 0 replicas when its first measured run started" | reproduces B12 |
| Summary: other commits and smoke runs left out | **failed**: "summarised 5 runs" | reproduces B12 |
| Chart: missing group shown as missing | **failed**: drawn as a 0 bar | reproduces B13 |

Not run here: the contract tests (need the k3d cluster), the .NET and Java unit and architecture tests, and `make arch` (no Docker daemon).

To run the steps from the repo root (`bdd/steps/conftest.py` sets the import path):

```bash
make doctor   # installs pytest-bdd 9.0.0 from requirements-host.txt
make bdd      # check_hexagonal.py bdd, then the scenarios in bdd/steps
```

Update after this review: the four failing scenarios are now tagged `@known-defect` and run as strict expected failures, so `make bdd` reports `5 passed, 4 xfailed` today. When a defect is fixed its scenario passes, strict mode reports that as a failure, and the tag comes off.

## Appendix — new feature files

The same files live in `bdd/features/`; the steps are in `bdd/steps/`.

### `bdd/features/exp3_booking_request_validation.feature`

```gherkin
@exp3 @validation @spec-exp3-L62-71 @rule-G1 @rule-G8
Feature: Malformed booking requests are refused identically by every stack
  As the experimenter comparing three stacks
  I want every stack to refuse the same malformed requests in the same way
  So that differences in the results come from the retry behaviour, not from input handling

  # Traces to: docs/exp3-spec.md lines 62-71, contract test 7, CLAUDE.md rules G1 and G8.
  # Rows tagged @open-question encode a proposed answer to a question the spec leaves open;
  # they are expected to fail on at least one stack today (see BDD_REVIEW.md, finding B11).

  Background:
    Given the booking service for the stack under test is running

  @contract-7 @failure
  Scenario Outline: A malformed booking is refused and nothing is recorded
    When the client sends a <endpoint> booking with <defect>
    Then the request is refused as invalid
    And no new booking or charge is recorded

    Examples: Covered today by contracts/tests/test_validation.py
      | endpoint | defect                      |
      | naive    | the owner missing           |
      | naive    | an unknown extra field      |
      | naive    | a negative deposit          |
      | naive    | a zero deposit              |
      | naive    | the deposit as quoted text  |
      | keyed    | the owner missing           |
      | keyed    | an unknown extra field      |
      | keyed    | a negative deposit          |
      | keyed    | a zero deposit              |
      | keyed    | the deposit as quoted text  |

    @open-question
    Examples: Not covered today; stacks are likely to disagree
      | endpoint | defect                          |
      | keyed    | an empty client reference       |
      | keyed    | a fractional deposit of 2500.5  |
      | keyed    | the deposit as true             |
      | keyed    | a null dog                      |
      | keyed    | field names in upper case       |
      | keyed    | a body that is not JSON         |

  @open-question @failure
  Scenario: A keyed booking with both a malformed body and no request key is refused for the body
    When the client sends a keyed booking with an unknown extra field and no request key
    Then the request is refused as invalid
    And no new booking or charge is recorded
```

### `bdd/features/exp3_fault_injection.feature`

```gherkin
@exp3 @fault-hook @spec-exp3-L108-119
Feature: The fault hook delays a committed confirmation only when injection is enabled
  As the experimenter
  I want to lose the confirmation of an already committed booking on demand
  So that the client's retry meets a booking that already exists

  # Traces to: docs/exp3-spec.md lines 108-119 and contract test 8.
  # Timing scenarios start from a warmed-up service so a cold JIT or a fresh pod
  # cannot fail them (see BDD_REVIEW.md, finding B2).

  Background:
    Given the booking service for the stack under test has served a warm-up booking

  @contract-8 @happy
  Scenario: The fault header is ignored while injection is disabled
    Given fault injection is disabled on the stack under test
    When the client books with the hold-after-commit fault header
    Then the confirmation arrives in under 500 ms
    And exactly one booking exists for that request

  @fault-injection @happy
  Scenario: The fault header holds the confirmation after the booking commits
    Given fault injection is enabled with a 2000 ms hold
    When the client books with the hold-after-commit fault header
    Then the booking is recorded before the confirmation arrives
    And the confirmation arrives no sooner than 2000 ms after the request

  @fault-injection @edge
  Scenario: An unrecognised fault header value is ignored
    Given fault injection is enabled with a 2000 ms hold
    When the client books with the fault header value "something-else"
    Then the confirmation arrives in under 500 ms
```

### `bdd/features/exp3_idempotency_policy.feature`

```gherkin
@exp3 @treatment @application @spec-exp3-L87-106
Feature: The idempotency policy decides create, replay, conflict or in-flight
  As the application layer that owns the idempotency policy
  I want every outcome decided from the stored request key alone
  So that each stack behaves identically without SQL, HTTP or framework types in the policy

  # Traces to: docs/exp3-spec.md lines 87-106 and CLAUDE.md (rules G2, G3).
  # Level: application service with the in-memory BookingStore (unit stage of each stack),
  # plus one inbound-adapter scenario with the driving port stubbed.

  @unit @happy
  Scenario: A fresh request key creates one booking and stores its result
    Given no booking has been made with request key "k1"
    When the service books with request key "k1"
    Then the outcome is a new booking
    And request key "k1" stores that booking's confirmation and request fingerprint

  @unit @inflight @spec-exp3-L100-101
  Scenario: A claimed request key with no stored result is reported as in flight
    Given request key "k1" is claimed for the same request but has no stored result
    When the service books with request key "k1"
    Then the outcome is in flight
    And no booking or charge is recorded

  @unit @failure @atomicity @rule-G3
  Scenario: A booking that fails part-way leaves no trace
    Given recording the deposit charge will fail once
    When the service books with request key "k1"
    Then the booking fails
    And no booking, no charge and no claim on request key "k1" remain

  @unit @failure @atomicity @rule-G3
  Scenario: A request key from a failed attempt can be used again
    Given an earlier booking with request key "k1" failed part-way
    When the service books with request key "k1"
    Then the outcome is a new booking
    And exactly one booking and one deposit charge exist for request key "k1"

  @adapter @inflight @spec-exp3-L100-101
  Scenario: An in-flight outcome tells the client to retry after one second
    Given the booking use case will report request key "k1" as in flight
    When the client books with request key "k1"
    Then the client is told the booking is still in flight and to retry after 1 second
    And the in-flight anomaly appears in the service log
```

### `bdd/features/exp3_idempotent_booking.feature`

```gherkin
@exp3 @treatment @spec-exp3-L81-106
Feature: A retried booking with the same request key is never booked or charged twice
  As a client whose confirmation can be lost on the way back
  I want a retry that carries the same request key to return the original confirmation
  So that a dog owner is booked and charged exactly once

  # Traces to: docs/exp3-spec.md lines 81-106 (POST /v2/bookings) and contract tests 3-6.
  # Level: HTTP contract, run against the stack named by STACK (make contract).
  # Every scenario creates its own request key and client reference, so scenarios
  # never depend on each other or on a truncated schema.

  Background:
    Given the booking service for the stack under test is running

  @contract-4 @happy
  Scenario: A first booking with a fresh request key is confirmed once
    Given a fresh request key
    When the client books session "s-42" for dog "d-7" with a 2500-cent deposit
    Then the client receives a new booking confirmation
    And exactly one booking and one 2500-cent deposit charge exist for that request

  @contract-4 @happy
  Scenario: Retrying with the same request key replays the original confirmation
    Given the client has booked session "s-42" with a fresh request key
    When the client retries the identical booking with the same request key
    Then the client receives the original confirmation marked as a replay
    And exactly one booking and one deposit charge exist for that request

  @fault-injection @spec-exp3-L108-119
  Scenario: A confirmation lost after the booking commits does not double-book the retry
    Given fault injection is enabled on the stack under test
    And the client's first attempt will lose its confirmation after the booking commits
    When the client books with a fresh request key and retries after the timeout
    Then the client receives a confirmation marked as a replay
    And exactly one booking and one deposit charge exist for that request

  @contract-5 @failure
  Scenario Outline: Reusing a request key for a different booking is refused as a conflict
    Given the client has booked session "s-42" with a fresh request key
    When the client books again with the same request key but a different <detail>
    Then the booking is refused as a request-key conflict
    And still exactly one booking and one deposit charge exist for that request key

    Examples:
      | detail           |
      | client reference |
      | session          |
      | dog              |
      | owner            |
      | deposit amount   |

  @contract-6 @edge
  Scenario: Twenty simultaneous duplicates produce exactly one booking
    When 20 identical bookings with the same fresh request key arrive at the same time
    Then all 20 clients receive the same booking confirmation
    And exactly one of those confirmations is not marked as a replay
    And exactly one booking and one deposit charge exist for that request

  @contract-3 @failure @spec-exp3-L83-84
  Scenario Outline: A booking without a usable request key is refused
    When the client books with <key>
    Then the booking is refused because a request key is required
    And no booking or charge is recorded for that client reference

    Examples:
      | key                                     |
      | no request key                          |
      | an empty request key                    |
      | a 256-character request key             |
      | a request key containing a space        |
      | a request key containing a non-ASCII letter |

  @edge @spec-exp3-L83
  Scenario: The longest permitted request key is accepted
    When the client books with a 255-character request key
    Then the client receives a new booking confirmation
    And exactly one booking and one deposit charge exist for that request
```

### `bdd/features/exp3_measurement_run.feature`

```gherkin
@exp3 @harness @spec-exp3-L121-153
Feature: Measured runs produce trustworthy evidence
  As the author who will publish duplicate counts
  I want every measured run to start clean, load a serving stack and refuse to record a failed run
  So that results/exp3 only ever holds valid measurements

  # Traces to: docs/exp3-spec.md lines 121-164 (load, measurement, run matrix, output files)
  # and CLAUDE.md rule H1. Level: harness/*.py with kubectl, k6 and Postgres replaced by
  # in-process fakes, so these scenarios run in seconds without a cluster.

  @matrix @regression @failure
  Scenario Outline: Only the stack under test serves traffic during its runs
    Given the matrix has finished measuring <earlier>
    When the matrix starts measuring <stack>
    Then <stack> has 1 replica
    And every other stack has 0 replicas

    Examples:
      | earlier       | stack  |
      | no stack yet  | dotnet |
      | dotnet        | java   |
      | java          | python |

  @run @failure
  Scenario: A run in which no booking was recorded is rejected, not appended
    Given the stack under test answers no requests
    When a measured run completes
    Then the run is reported as invalid
    And no row is appended to the run log

  @run @happy
  Scenario: A measured run starts from empty tables
    Given the stack's tables hold bookings from an earlier run
    When a measured run starts
    Then the stack's bookings, charges and request keys are empty before load begins

  @run @happy
  Scenario Outline: Duplicates and losses are counted in the database
    Given a run sent <logical> logical requests
    And the database holds <total> bookings for <distinct> distinct client references
    When the run is counted
    Then the run records <duplicates> duplicate bookings and <lost> lost requests

    Examples:
      | logical | total | distinct | duplicates | lost |
      | 10000   | 10500 | 10000    | 500        | 0    |
      | 10000   | 10000 | 10000    | 0          | 0    |
      | 10000   | 9990  | 9990     | 0          | 10   |

  @load @edge
  Scenario Outline: The same logical requests are faulted in every stack and run
    When <total> logical requests are planned at a <rate> fault rate
    Then exactly <faulted> first attempts carry the fault header
    And the faulted request numbers are the same for every stack and run

    Examples:
      | total | rate | faulted |
      | 10000 | 0    | 0       |
      | 10000 | 0.01 | 100     |
      | 10000 | 0.05 | 500     |

  @matrix @happy
  Scenario: A resumed matrix skips runs already recorded for this commit
    Given the run log holds all 18 dotnet runs for the current commit
    When the matrix is planned
    Then 36 runs are planned
    And dotnet is not warmed up again

  @matrix @happy
  Scenario: A dry run plans the matrix without touching the cluster
    When the matrix is planned as a dry run
    Then 54 runs and 3 warm-ups are listed with an estimated duration
    And no cluster or load command is executed

  @open-question @run
  Scenario: Switching fault injection on keeps the warmed-up process
    Given the stack under test has been warmed up
    When fault injection is switched on for a measured run
    Then the measured run is served by the warmed-up process

  @hostinfo @failure
  Scenario: Host details name the machine architecture
    Given the host is an arm64 machine
    When host details are captured
    Then the operating-system entry ends with "(arm64)"
```

### `bdd/features/exp3_naive_baseline.feature`

```gherkin
@exp3 @control @spec-exp3-L73-79
Feature: The naive booking baseline books every attempt, by design
  As the experimenter
  I want the control group to create a booking and a charge for every attempt
  So that duplicates under retry can be measured against the keyed endpoint

  # Traces to: docs/exp3-spec.md lines 73-79, .claude/rules/naive-baseline.md, contract test 2.
  # A result of "two bookings" here is the expected behaviour, not a bug. Do not "fix" it.

  Background:
    Given the booking service for the stack under test is running

  @contract-2 @happy
  Scenario: A repeated naive booking creates a second booking and a second charge
    Given the client has booked session "s-42" on the naive endpoint
    When the client sends the identical naive booking again
    Then the client receives a different booking confirmation
    And two bookings and two deposit charges exist for that client reference

  @fault-injection @spec-exp3-L108-119
  Scenario: A confirmation lost after commit double-charges on the naive endpoint
    Given fault injection is enabled on the stack under test
    And the client's first attempt will lose its confirmation after the booking commits
    When the client books on the naive endpoint and retries after the timeout
    Then two bookings and two deposit charges exist for that client reference

  @happy
  Scenario: The naive endpoint ignores a request key
    When the client books on the naive endpoint with a fresh request key
    Then the client receives a new booking confirmation
    And no request key is stored
```

### `bdd/features/exp3_results_summary_and_chart.feature`

```gherkin
@exp3 @results @spec-exp3-L155-177 @rule-H1 @rule-H4
Feature: The summary and chart are derived only from valid, full-length runs of one commit
  As the author who will put the chart in an article
  I want the summary and chart to reflect exactly the measured runs of one commit
  So that no stale, smoke or synthetic number can reach a reader

  # Traces to: docs/exp3-spec.md lines 155-177 and CLAUDE.md rules H1 and H4.
  # Level: harness/exp3_summary.py and figures/exp3_duplicates.py on fixture files in tmp_path.

  @summary @failure
  Scenario: Runs from other commits and shortened smoke runs are left out
    Given the run log holds 3 full-length runs of dotnet naive at 5% for commit A
    And a 500-request smoke run of dotnet naive at 5% for commit A
    And 1 full-length run of dotnet naive at 5% for commit B
    When the summary is built for commit A
    Then the dotnet naive 5% group summarises exactly the 3 full-length runs

  @summary @failure
  Scenario: The summary is refused while any run is invalid
    Given the run log holds a run that recorded no bookings
    When the summary is built
    Then the summary is refused and names that run
    And no summary file is written

  @summary @happy
  Scenario Outline: Each group reports the median and range of duplicates per 10,000 requests
    Given three full-length runs of a group recorded <duplicates> duplicate bookings out of 10000 logical requests
    When the summary is built
    Then the group's median is <median> per 10,000 and its range is <range>

    Examples:
      | duplicates  | median | range      |
      | 99, 100, 99 | 99.0   | 99.0-100.0 |
      | 0, 0, 0     | 0.0    | 0.0-0.0    |

  @summary @happy
  Scenario: The latency overhead of the request key is reported at fault rate 0
    Given dotnet runs at fault rate 0 have a median p99 of 8 ms naive and 10 ms keyed
    When the summary is built
    Then dotnet's p99 overhead is 2 ms

  @chart @happy
  Scenario: Every bar is labelled with its value, including zero
    Given a summary with every stack, variant and fault rate
    When the chart is drawn
    Then every bar is labelled with its median, including the keyed bars at 0.0

  @chart @failure
  Scenario: A group with no data is shown as missing, not as zero
    Given a summary with no java rows at a 1% fault rate
    When the chart is drawn
    Then the java 1% bars are labelled "no data"

  @chart @failure @rule-H4
  Scenario: The synthetic fixture can never become the published chart
    Given the input is the labelled synthetic fixture
    When the chart is drawn to the published chart's location
    Then drawing is refused because the input is synthetic
```

### `bdd/features/exp3_service_health.feature`

```gherkin
@exp3 @health @contract-1 @spec-exp3-L71
Feature: The health check names the stack that answers
  As the operator running the matrix
  I want each service to say which stack it is
  So that load is never sent to the wrong stack

  # Traces to: docs/exp3-spec.md line 71 and contract test 1.

  @happy
  Scenario: The health check reports ok and the stack's name
    Given the booking service for the stack under test is running
    When the operator checks the service's health
    Then the service reports it is ok and names the stack under test
```
