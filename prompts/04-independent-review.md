# P4. Independent review

**When:** Sat 10 Oct, after P3 and before the full matrix run, so fixes land before you measure.
**Session:** a **new** Claude Code session. Do not reuse a build session; the reviewer should not
have watched the code being written.

## Prompt (paste as is)

```text
You are a sceptical principal engineer reviewing this repo before it goes public. Do not edit any file.

Read CLAUDE.md, docs/exp3-spec.md and all code under stacks/, contracts/, harness/, infra/ and figures/. Run python3 tools/arch/check_hexagonal.py --all, python3 tools/arch/check_hexagonal.py --all --complete (README.md and results not produced yet are expected to be missing; anything else is a finding) and make arch for each stack, and include their output. Report findings ranked by severity:

1. Any way /v2/bookings in any stack can still create a duplicate booking or charge: races, transaction boundaries, the replay path, the request hash, error handling, connection-pool behaviour.
2. Any way the naive baseline is accidentally protected (unique constraints, retries, framework behaviour), which would understate the problem.
3. Hexagonal leaks the checkers cannot see: framework or driver types in port signatures; SQL, HTTP status codes or JSON in the application layer; transaction control in use cases; adapters reaching into each other through bootstrap or shared globals; domain logic living in adapters; ports shaped around one database rather than the use case.
4. Differences between stacks that make the comparison unfair: pool sizes, limits, timeouts, JSON handling, logging levels, warm-up, or different port and use-case shapes.
5. Measurement errors: how duplicates and losses are counted, fault selection, k6 retries, dropped iterations, truncation between runs.
6. Reproducibility gaps: anything make up needs that make doctor does not check, unpinned versions, absolute paths, secrets.
7. Listed files that are still stubs or nearly empty, and anything that belongs in a file the CLAUDE.md tree does not list.

For each finding give the file and line, a concrete failure scenario, and the smallest fix. Then list what you checked and found sound.
```

## Then

Take the findings back to a build session one at a time, with the review-finding prompt in `prompts/README.md`.
