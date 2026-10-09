---
description: The naive booking baseline is the experiment's control group; never make it correct
globs: stacks/python/src/booking/application/services/book_session_naive.py,stacks/python/src/booking/adapters/inbound/http/routes_naive.py,stacks/java/booking-application/src/main/java/work/rajc/booking/application/service/BookSessionNaiveService.java,stacks/java/booking-adapter-in-http/src/main/java/work/rajc/booking/adapter/in/http/NaiveBookingController.java,stacks/dotnet/src/Rajc.Bookings.Application/Services/BookSessionNaiveService.cs,stacks/dotnet/src/Rajc.Bookings.Adapters.Inbound.Http/NaiveBookingEndpoints.cs
---

# INTENTIONALLY NAIVE BASELINE — do not fix

These files are the control group for experiment 3. Duplicates under retry are the
measurement; making the baseline idempotent would destroy the experiment.

- No idempotency key, no deduplication, no retries, no locks, no unique constraints.
- One transaction: insert booking, insert charge, commit. That is all.
- Exempt from rule G2 only; every other rule still applies.
- Keep the "INTENTIONALLY NAIVE BASELINE" header comment in each file.

If a test fails because the naive endpoint misbehaves (for example it creates a second
booking on retry), that is the point. Do not "fix" it; tell the author instead.
