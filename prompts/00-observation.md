# P0. Observation: what Claude Code writes when asked plainly

**When:** Fri 9 Oct, 17:00 to 17:45 IST, before anything else.
**Feeds:** article section 6. Run once per stack.

This output is **not** the experiment's naive baseline (that is specified exactly in
`docs/exp3-spec.md`). It is an honest record of default behaviour, so it must be produced
without any of this repo's instructions in context.

## Setup, per stack

1. Make an empty folder outside the repo, for example `~/scratch/obs-python`. There must be no
   `CLAUDE.md` or `AGENTS.md` in it or in any folder above it.
2. Start Claude Code there with auto memory off:
   `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 claude`
3. If you have a personal `~/.claude/CLAUDE.md`, it still loads. Note that in META.md; remove it
   temporarily only if you want a cleaner observation.
4. Paste the prompt below exactly. If Claude Code asks a question, reply only: `Use your judgement.`
   Accept its plan. Add no other instructions.
5. When it says it is done, stop. Do not ask for fixes.

## The prompts (identical except the stack)

Python:

```text
Create a FastAPI service with a POST /bookings endpoint that books a dog-training session and charges a deposit (simulated, no real payment provider), storing the booking and the charge in PostgreSQL.
```

.NET:

```text
Create a .NET 10 minimal API service with a POST /bookings endpoint that books a dog-training session and charges a deposit (simulated, no real payment provider), storing the booking and the charge in PostgreSQL.
```

Java:

```text
Create a Spring Boot 4 service on Java 25 with a POST /bookings endpoint that books a dog-training session and charges a deposit (simulated, no real payment provider), storing the booking and the charge in PostgreSQL.
```

## Record (you do this, not Claude Code)

1. Copy the folder into the repo at `observations/exp3/<stack>/output/`. Claude Code is blocked
   from editing `observations/`, which is the point.
2. Write `observations/exp3/<stack>/META.md` with:
   - date and time (IST), output of `claude --version`, and the model shown in the session
   - the exact prompt, every question Claude Code asked, and your replies
   - whether a personal `~/.claude/CLAUDE.md` was loaded
3. Answer in META.md, each with yes or no plus file and line:
   1. Does `POST /bookings` accept or require an idempotency key?
   2. Are the booking and the charge written in one transaction?
   3. Does anything stop a retried request from creating a second booking (unique constraint, key, deduplication)?
   4. Does the endpoint return the persistence entity directly? (rule 1, for post 4)
   5. Is there any retry logic, and where?
4. Commit: `docs(observations): exp3 default output for <stack>`.

If the default output already uses an idempotency key, record that plainly. It is a finding too.
